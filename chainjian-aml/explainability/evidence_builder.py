"""Build a normalized, evidence-only chain for an APP alert."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools import get_alert_detail, get_transaction_evidence, get_transaction_path
from core.warehouse import DEFAULT_DATABASE
from risk_profile.profile_service import AccountProfileService


class EvidenceBuilder:
    """Collect Alert, Neo4j, DWD and DWS facts without using an LLM."""

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def build(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        profile = AccountProfileService(self.warehouse_path).get(alert["account_id"])
        transactions = get_transaction_evidence(alert_id, self.warehouse_path)
        paths = get_transaction_path(alert["account_id"], max_hops=3)
        by_id = {row["transaction_id"]: row for row in transactions}
        evidence: list[dict[str, Any]] = []
        for item in alert.get("evidence", []):
            content = item.get("evidence_content", {})
            tx_rows = [self._transaction(by_id[tx_id]) for tx_id in content.get("transactions", []) if tx_id in by_id]
            evidence_type = str(item.get("evidence_type", "alert_evidence"))
            if "cycle" in evidence_type or "circular" in evidence_type or "CYCLE" in " ".join(alert.get("rule_hits", [])):
                evidence.append({"type": "cycle_transaction", "description": "发现预警证据中的资金回流路径", "path": content.get("path", "->".join(content.get("account_path", []))), "transactions": tx_rows, "source": "APP alert_evidence"})
            elif "rapid" in evidence_type or "RAPID_MOVEMENT" in alert.get("rule_hits", []):
                evidence.append({"type": "rapid_movement", "description": "发现预警证据中的快速资金转移", "holding_time": content.get("holding_time_minutes"), "in_transaction": content.get("in_transaction"), "out_transaction": content.get("out_transaction"), "outflow_ratio": content.get("outflow_ratio"), "transactions": tx_rows, "source": "APP alert_evidence"})
            else:
                evidence.append({"type": evidence_type, "description": "预警规则保存的关联交易证据", "path": content.get("path"), "transactions": tx_rows, "source": "APP alert_evidence"})
        if paths:
            evidence.append({"type": "graph_path", "description": "Neo4j 返回的账户 1–3 跳资金路径", "paths": paths, "path_count": len(paths), "source": "Neo4j"})
        return {"alert_id": alert_id, "account_id": alert["account_id"], "alert": {"risk_level": alert["risk_level"], "risk_score": alert["risk_score"], "rule_hits": alert["rule_hits"], "status": alert["status"]}, "evidence": evidence, "transactions": transactions, "paths": paths, "account_profile": profile, "sources": ["APP alert_case", "APP alert_evidence", "DWD dwd_transaction_detail", "DWS account profile", "Neo4j TRANSFER"]}

    @staticmethod
    def _transaction(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["transaction_id"], "amount": row["amount_paid"], "time": row["timestamp"], "payer": row["from_account_id"], "receiver": row["to_account_id"], "currency": row["payment_currency"]}
