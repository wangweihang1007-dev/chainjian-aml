"""Supervisor that dynamically assigns specialist AML agents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent.tools import get_alert_detail, get_risk_response, get_transaction_evidence
from agents.graph_agent import GraphAgent
from agents.report_agent import ReportAgent
from agents.rule_agent import RuleAgent
from agents.task_store import InvestigationTaskStore
from agents.transaction_agent import TransactionAgent
from core.warehouse import DEFAULT_DATABASE
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from risk_profile.profile_service import AccountProfileService


class SupervisorAgent:
    """Run only specialists relevant to the alert, then aggregate their evidence."""

    name = "Supervisor Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm=None) -> None:
        self.warehouse_path = warehouse_path
        self.tasks = InvestigationTaskStore(warehouse_path)
        self.rule_agent = RuleAgent(warehouse_path)
        self.graph_agent = GraphAgent(warehouse_path)
        self.transaction_agent = TransactionAgent(warehouse_path)
        self.report_agent = ReportAgent(warehouse_path, llm)

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
        for task in task_plan:
            task_id = ids[task["task_id"]]
            self.tasks.start(task_id)
            try:
                if task["task_id"] == "report":
                    outputs["transaction_evidence"] = get_transaction_evidence(alert_id, self.warehouse_path)
                    outputs["risk_response"] = get_risk_response(alert_id, self.warehouse_path)
                    chain = EvidenceBuilder(self.warehouse_path).build(alert_id)
                    outputs["explainability"] = {"evidence_chain": chain, "risk_explanation": RiskExplainer().explain(chain), "score_explanation": ScoreExplainer().explain(chain)}
                    report_input = dict(outputs)
                    report_input["transaction_paths"] = outputs.get("graph_analysis", {}).get("paths", [])
                    report_input["risk_conclusion"] = {
                        "risk_level": alert["risk_level"],
                        "risk_score": alert["risk_score"],
                        "rule_hits": alert.get("rule_hits", []),
                        "evidence_transaction_ids": [item["transaction_id"] for item in outputs["transaction_evidence"]],
                        "conclusion": "结论仅基于预警、规则 Agent、图谱 Agent、交易 Agent 返回的事实证据。",
                    }
                    output = self.report_agent.run(report_input)
                    outputs["report"] = output
                else:
                    output = runners[task["task_id"]]()
                    outputs[task["task_id"] + "_analysis"] = output
                self.tasks.finish(task_id, "COMPLETED", output)
            except Exception as error:
                output = {"error": str(error)}
                outputs[task["task_id"] + "_error"] = str(error)
                self.tasks.finish(task_id, "FAILED", output)
        return {"alert_id": alert_id, "supervisor": self.name, "tasks": self.tasks.list(alert_id), "results": outputs, "explainability": outputs.get("explainability", {}), "report": outputs.get("report", {}).get("report", "")}

    def get_tasks(self, alert_id: str) -> list[dict[str, Any]]:
        return self.tasks.list(alert_id)

    def run(self, user_input: str) -> dict[str, Any]:
        match = re.search(r"\bAL\d+\b", user_input.upper())
        if not match:
            raise ValueError("Please provide an alert ID, for example: 分析 AL000001")
        return self.investigate(match.group())
