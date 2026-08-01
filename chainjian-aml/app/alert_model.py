"""Canonical APP-layer AML alert case models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AlertEvidence:
    evidence_id: str
    alert_id: str
    evidence_type: str
    evidence_content: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlertCase:
    alert_id: str
    account_id: str
    risk_score: float
    risk_level: str
    rule_hits: list[str]
    evidence: list[AlertEvidence]
    status: str
    created_time: str

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [item.as_dict() for item in self.evidence]
        return result
