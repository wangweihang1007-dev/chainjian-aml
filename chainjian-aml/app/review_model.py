"""Review workflow records for AML alert cases."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    alert_id: str
    reviewer: str
    action: str
    comment: str
    created_time: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class AuditLog:
    log_id: str
    alert_id: str
    operation: str
    operator: str
    timestamp: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
