"""Shared, serializable rule output models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RuleHit:
    rule_code: str
    severity: int
    explanation: str


@dataclass(frozen=True)
class Evidence:
    evidence_type: str
    transaction_ids: list[str]
    account_path: list[str]
    details: dict[str, Any]


@dataclass(frozen=True)
class Alert:
    """The standard output shared by all AML rules."""

    alert_id: str
    account_id: str
    risk_score: float
    risk_level: str
    rule_hits: list[RuleHit]
    evidence: list[Evidence]
    created_time: str
    status: str = "pending"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
