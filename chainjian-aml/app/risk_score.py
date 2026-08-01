"""Transparent rule-weight risk scoring for AML alert cases."""

from __future__ import annotations


RULE_WEIGHTS = {
    "CYCLE_TRANSFER": 40,
    "CYCLE_TRANSACTION": 40,
    "STRUCTURING_TRANSFER": 30,
    "STRUCTURING_TRANSACTION": 30,
    "FAN_IN_COLLECTION": 25,
    "FAN_IN": 25,
    "MULTI_HOP_TRANSFER": 20,
}


def calculate_risk_score(rule_codes: list[str]) -> float:
    """Add distinct rule weights and cap the normalized score at 100."""
    return float(min(100, sum(RULE_WEIGHTS.get(code, 0) for code in set(rule_codes))))


def risk_level(score: float) -> str:
    if score >= 80:
        return "HIGH"
    if score >= 50:
        return "MEDIUM"
    return "LOW"
