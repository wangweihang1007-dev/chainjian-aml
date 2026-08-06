"""Build a review-only SAR draft from existing grounded AML facts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools import get_alert_detail, get_transaction_evidence
from core.warehouse import DEFAULT_DATABASE
from legal_research.reference_index import get_legal_basis

from .judge import judge_case
from .narrative import render_narrative


def build_sar_draft(alert_id: str, warehouse_path: Path = DEFAULT_DATABASE) -> dict[str, Any]:
    alert = get_alert_detail(alert_id, warehouse_path)
    if not alert:
        raise ValueError(f"Alert not found: {alert_id}")
    evidence = get_transaction_evidence(alert_id, warehouse_path)
    legal_basis = get_legal_basis(alert.get("rule_hits", []))
    judgment = judge_case(alert, evidence, legal_basis)
    return {
        "alert_id": alert_id,
        "judgment": judgment,
        "legal_basis": legal_basis,
        "report_markdown": render_narrative(alert, evidence, legal_basis, judgment),
        "submission_ready": False,
        "requires_human_approval": True,
    }
