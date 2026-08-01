"""Compatibility facade for transparent APP-layer risk scoring."""

from app.risk_score import calculate_risk_score, risk_level


def score_rule_hits(rule_codes: list[str]) -> dict[str, float | str]:
    score = calculate_risk_score(rule_codes)
    return {"risk_score": score, "risk_level": risk_level(score)}
