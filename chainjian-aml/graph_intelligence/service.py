"""Application service combining evidence subgraph, roles and timeline."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.alert_service import AlertService
from core.warehouse import DEFAULT_DATABASE

from graph_intelligence.evidence_subgraph import build_evidence_subgraph
from graph_intelligence.role_classifier import classify_roles
from graph_intelligence.temporal_flow import build_timeline
from graph_intelligence.counterfactual import analyze_counterfactual
from graph_intelligence.risk_propagation import propagate_associated_review
from graph_intelligence.persistence import load_result, save_result


class GraphIntelligenceService:
    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.alerts = AlertService(warehouse_path)

    def investigate(self, alert_id: str, max_hops: int = 3) -> dict:
        cached = load_result(self.alerts.warehouse_path, alert_id, max_hops)
        if cached:
            return cached
        alert = self.alerts.get_alert(alert_id)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        alert_data = alert.as_dict()
        subgraph = build_evidence_subgraph(alert_data, max_hops=max_hops)
        result = {
            "alert_id": alert_id,
            "account_id": alert.account_id,
            "risk_level": alert.risk_level,
            "risk_score": alert.risk_score,
            "rule_hits": alert.rule_hits,
            "evidence_subgraph": subgraph,
            "roles": classify_roles(subgraph),
            "timeline": build_timeline(subgraph),
            "counterfactual": analyze_counterfactual(subgraph),
            "associated_review": propagate_associated_review(subgraph, alert.account_id, max_hops=2),
        }
        save_result(self.alerts.warehouse_path, alert_id, max_hops, result)
        return result
