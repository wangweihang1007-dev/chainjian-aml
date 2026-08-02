"""Tool-grounded AML Investigation Agent with dynamic planning."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from agent.investigation_planner import InvestigationStep, build_plan
from agent.investigation_trace import InvestigationTraceStore
from agent.report_generator import generate_report
from agent.tools import get_alert_detail, get_risk_response, get_transaction_evidence, get_transaction_path
from core.warehouse import DEFAULT_DATABASE
from graph_intelligence.service import GraphIntelligenceService
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from counterfactual.analyzer import CounterfactualAnalyzer
from risk_profile.profile_service import AccountProfileService
from rules.rapid_movement_rule import RapidMovementRule


class InvestigationAgent:
    """Select and execute only evidence-backed investigation steps."""

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm: Callable[[str, dict[str, Any]], str] | None = None) -> None:
        self.warehouse_path = warehouse_path
        self.llm = llm
        self.trace_store = InvestigationTraceStore(warehouse_path)

    def investigate(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        profile = AccountProfileService(self.warehouse_path).get(alert["account_id"])
        plan = build_plan(alert, profile)
        results: dict[str, Any] = {"alert": alert, "profile": profile}
        plan_state = [step.as_dict() for step in plan]
        trace_ids = self.trace_store.initialize(alert_id, plan_state)
        for index, step in enumerate(plan):
            trace_id = trace_ids[step.step_id]
            self.trace_store.start(trace_id)
            plan_state[index]["status"] = "RUNNING"
            try:
                output = self._execute(step, results)
                results[step.tool_name] = output
                self.trace_store.finish(trace_id, "COMPLETED", output)
                plan_state[index]["status"] = "COMPLETED"
            except Exception as error:
                self.trace_store.finish(trace_id, "FAILED", {"error": str(error)})
                plan_state[index]["status"] = "FAILED"
                results[f"{step.tool_name}_error"] = str(error)

        report = results.get("generate_report", "")
        if "explainability" not in results:
            results["explainability"] = self._build_explainability(alert["alert_id"])
        if "counterfactual" not in results:
            results["counterfactual"] = CounterfactualAnalyzer(self.warehouse_path).analyze(alert["alert_id"])
        if not report:
            report = generate_report(self._report_data(results), self.llm)
        trace = self.trace_store.list(alert_id)
        return {"alert_id": alert_id, "plan": plan_state, "trace": trace, "tool_data": self._report_data(results), "explainability": results.get("explainability", {}), "counterfactual": results.get("counterfactual", {}), "report": report}

    def _execute(self, step: InvestigationStep, results: dict[str, Any]) -> Any:
        alert = results["alert"]
        account_id = alert["account_id"]
        if step.tool_name == "get_alert_detail":
            return alert
        if step.tool_name == "get_account_profile":
            return results["profile"]
        if step.tool_name == "get_transaction_path":
            return get_transaction_path(account_id, max_hops=3)
        if step.tool_name == "check_cycle_evidence":
            graph = GraphIntelligenceService(self.warehouse_path).investigate(alert["alert_id"])
            return {"counterfactual": graph.get("counterfactual", []), "edges": [edge for edge in graph.get("evidence_subgraph", {}).get("edges", []) if edge.get("evidence_type") == "direct_hit"]}
        if step.tool_name == "check_rapid_movement":
            findings = RapidMovementRule(self.warehouse_path).detect()
            return [finding.as_dict() for finding in findings if finding.account_id == account_id]
        if step.tool_name == "get_transaction_evidence":
            return get_transaction_evidence(alert["alert_id"], self.warehouse_path)
        if step.tool_name == "build_risk_conclusion":
            evidence = results.get("get_transaction_evidence", [])
            return {"risk_level": alert["risk_level"], "risk_score": alert["risk_score"], "rule_hits": alert["rule_hits"], "evidence_transaction_ids": [item["transaction_id"] for item in evidence], "conclusion": "Risk conclusion is limited to the configured rules and returned transaction evidence."}
        if step.tool_name == "get_risk_response":
            return get_risk_response(alert["alert_id"], self.warehouse_path)
        if step.tool_name == "generate_report":
            results["explainability"] = self._build_explainability(alert["alert_id"])
            results["counterfactual"] = CounterfactualAnalyzer(self.warehouse_path).analyze(alert["alert_id"])
            return generate_report(self._report_data(results), self.llm)
        raise ValueError(f"Unsupported investigation tool: {step.tool_name}")

    @staticmethod
    def _report_data(results: dict[str, Any]) -> dict[str, Any]:
        return {
            "alert": results["alert"],
            "account_profile": results.get("profile", {}),
            "transaction_paths": results.get("get_transaction_path", []),
            "transaction_evidence": results.get("get_transaction_evidence", []),
            "graph_intelligence": results.get("check_cycle_evidence", {}),
            "risk_response": results.get("get_risk_response", {}),
            "risk_conclusion": results.get("build_risk_conclusion", {}),
            "explainability": results.get("explainability", {}),
            "counterfactual": results.get("counterfactual", {}),
        }

    def _build_explainability(self, alert_id: str) -> dict[str, Any]:
        chain = EvidenceBuilder(self.warehouse_path).build(alert_id)
        return {"evidence_chain": chain, "risk_explanation": RiskExplainer().explain(chain), "score_explanation": ScoreExplainer().explain(chain)}

    def get_trace(self, alert_id: str) -> list[dict[str, Any]]:
        return self.trace_store.list(alert_id)

    def run(self, user_input: str) -> dict[str, Any]:
        match = re.search(r"\bAL\d+\b", user_input.upper())
        if not match:
            raise ValueError("Please provide an alert ID, for example: 分析 AL000001")
        return self.investigate(match.group())
