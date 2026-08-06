"""Supervisor that dynamically assigns specialist AML agents."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from agent.tools import get_alert_detail, get_risk_response, get_transaction_evidence
from agents.graph_agent import GraphAgent
from agents.report_agent import ReportAgent
from agents.rule_agent import RuleAgent
from agents.task_store import InvestigationTaskStore
from agent.llm_client import configured_llm, llm_status
from agents.transaction_agent import TransactionAgent
from core.warehouse import DEFAULT_DATABASE
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from counterfactual.analyzer import CounterfactualAnalyzer
from risk_profile.profile_service import AccountProfileService
from agents.evidence import build_evidence_index
from agents.evidence_judge import EvidenceJudge


class SupervisorAgent:
    """Run only specialists relevant to the alert, then aggregate their evidence."""

    name = "Supervisor Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm=None) -> None:
        self.warehouse_path = warehouse_path
        self.tasks = InvestigationTaskStore(warehouse_path)
        self.rule_agent = RuleAgent(warehouse_path)
        self.graph_agent = GraphAgent(warehouse_path)
        self.transaction_agent = TransactionAgent(warehouse_path)
        self.report_agent = ReportAgent(warehouse_path, llm or configured_llm()[1])
        self.evidence_judge = EvidenceJudge()

    def _task_plan(self, alert: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
        hits = set(alert.get("rule_hits", []))
        tasks = [{"task_id": "rule", "agent_name": "Rule Agent", "task_type": "rule_analysis", "input": {"alert_id": alert["alert_id"]}}]
        if hits & {"CYCLE_TRANSFER", "FAN_IN_COLLECTION", "MULTI_HOP_TRANSFER"} or alert.get("risk_level") == "HIGH":
            tasks.append({"task_id": "graph", "agent_name": "Graph Agent", "task_type": "graph_analysis", "input": {"account_id": alert["account_id"], "max_hops": 3}})
        if hits & {"RAPID_MOVEMENT"} or {"高频交易", "资金快进快出", "大额资金流出"} & set(profile.get("risk_features", [])):
            tasks.append({"task_id": "transaction", "agent_name": "Transaction Agent", "task_type": "transaction_analysis", "input": {"account_id": alert["account_id"]}})
        tasks.append({"task_id": "report", "agent_name": "Report Agent", "task_type": "report_generation", "input": {"alert_id": alert["alert_id"]}})
        return tasks

    def investigate(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        profile = AccountProfileService(self.warehouse_path).get(alert["account_id"])
        task_plan = self._task_plan(alert, profile)
        ids = self.tasks.initialize(alert_id, task_plan)
        outputs: dict[str, Any] = {"alert": alert, "account_profile": profile}
        runners = {"rule": lambda: self.rule_agent.run(alert_id), "graph": lambda: self.graph_agent.run(alert["account_id"]), "transaction": lambda: self.transaction_agent.run(alert["account_id"])}
        specialist_tasks = [task for task in task_plan if task["task_id"] != "report"]
        outputs["orchestration"] = {"mode": "parallel_dag", "parallel_tasks": [task["task_id"] for task in specialist_tasks], "max_supplement_rounds": 1}

        def execute(task: dict[str, Any]) -> tuple[str, Any]:
            task_id = ids[task["task_id"]]
            self.tasks.start(task_id)
            try:
                output = runners[task["task_id"]]()
                self.tasks.finish(task_id, "COMPLETED", output)
                return task["task_id"], output
            except Exception as error:
                failure = {"error": str(error), "degraded": True}
                self.tasks.finish(task_id, "FAILED", failure)
                return task["task_id"], failure

        with ThreadPoolExecutor(max_workers=max(1, len(specialist_tasks))) as pool:
            futures = [pool.submit(execute, task) for task in specialist_tasks]
            for future in as_completed(futures):
                task_key, output = future.result()
                if "error" in output:
                    outputs[task_key + "_error"] = output["error"]
                else:
                    outputs[task_key + "_analysis"] = output

        evidence = build_evidence_index(outputs)
        outputs["evidence"] = evidence
        outputs["evidence_judgement"] = self.evidence_judge.evaluate(alert, outputs, evidence)
        # One bounded supplement round prevents runaway agent loops while still
        # allowing a failed specialist to be retried when evidence is insufficient.
        if outputs["evidence_judgement"]["needs_more_evidence"]:
            supplement = next((task for task in specialist_tasks if task["task_id"] + "_error" in outputs), None)
            if supplement:
                task_id = ids[supplement["task_id"]]
                outputs["orchestration"]["supplement_round"] = supplement["task_id"]
                self.tasks.start(task_id)
                try:
                    retry = runners[supplement["task_id"]]()
                    outputs[supplement["task_id"] + "_analysis"] = retry
                    outputs.pop(supplement["task_id"] + "_error", None)
                    self.tasks.finish(task_id, "COMPLETED", retry)
                    outputs["evidence"] = build_evidence_index(outputs)
                    outputs["evidence_judgement"] = self.evidence_judge.evaluate(alert, outputs, outputs["evidence"])
                except Exception as error:
                    outputs["evidence_judgement"]["issues"].append(f"补查失败：{error}")

        report_task = next(task for task in task_plan if task["task_id"] == "report")
        report_id = ids["report"]
        self.tasks.start(report_id)
        try:
            task = report_task
            if task["task_id"] == "report":
                    outputs["transaction_evidence"] = get_transaction_evidence(alert_id, self.warehouse_path)
                    outputs["risk_response"] = get_risk_response(alert_id, self.warehouse_path)
                    chain = EvidenceBuilder(self.warehouse_path).build(alert_id)
                    outputs["explainability"] = {"evidence_chain": chain, "risk_explanation": RiskExplainer().explain(chain), "score_explanation": ScoreExplainer().explain(chain)}
                    outputs["counterfactual"] = CounterfactualAnalyzer(self.warehouse_path).analyze(alert_id)
                    report_input = dict(outputs)
                    report_input["transaction_paths"] = outputs.get("graph_analysis", {}).get("paths", [])
                    report_input["risk_conclusion"] = {
                        "risk_level": alert["risk_level"],
                        "risk_score": alert["risk_score"],
                        "rule_hits": alert.get("rule_hits", []),
                        "evidence_transaction_ids": [item["transaction_id"] for item in outputs["transaction_evidence"]],
                        "conclusion": "结论仅基于预警、规则 Agent、图谱 Agent、交易 Agent 返回的事实证据。",
                    }
                    report_input["evidence"] = outputs["evidence"]
                    report_input["evidence_judgement"] = outputs["evidence_judgement"]
                    output = self.report_agent.run(report_input)
                    outputs["report"] = output
            self.tasks.finish(report_id, "COMPLETED", output)
        except Exception as error:
            output = {"error": str(error), "degraded": True}
            outputs["report_error"] = str(error)
            self.tasks.finish(report_id, "FAILED", output)
        return {"alert_id": alert_id, "supervisor": self.name, "tasks": self.tasks.list(alert_id), "results": outputs, "explainability": outputs.get("explainability", {}), "counterfactual": outputs.get("counterfactual", {}), "ai": llm_status(), "report": outputs.get("report", {}).get("report", "")}

    def get_tasks(self, alert_id: str) -> list[dict[str, Any]]:
        return self.tasks.list(alert_id)

    def run(self, user_input: str) -> dict[str, Any]:
        match = re.search(r"\bAL\d+\b", user_input.upper())
        if not match:
            raise ValueError("Please provide an alert ID, for example: 分析 AL000001")
        return self.investigate(match.group())
