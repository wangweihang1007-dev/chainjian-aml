"""Deterministic SAR-draft triage gate."""

from __future__ import annotations

from typing import Any


def judge_case(alert: dict[str, Any], evidence: list[dict[str, Any]], legal_basis: list[dict[str, Any]]) -> dict[str, Any]:
    high_risk = str(alert.get("risk_level", "")).upper() == "HIGH" or float(alert.get("risk_score") or 0) >= 80
    enough_evidence = bool(evidence) and bool(alert.get("rule_hits"))
    decision = "DRAFT_SAR" if high_risk and enough_evidence else "INVESTIGATION_CONTINUES"
    return {
        "decision": decision,
        "review_required": True,
        "submission_ready": False,
        "reason_codes": ["HIGH_RISK" if high_risk else "RISK_BELOW_SAR_GATE", "EVIDENCE_PRESENT" if enough_evidence else "INSUFFICIENT_EVIDENCE"],
        "legal_basis_count": len(legal_basis),
        "disclaimer": "该判定仅用于生成 SAR 草案，不构成洗钱认定、法律意见或监管报送决定。",
    }
