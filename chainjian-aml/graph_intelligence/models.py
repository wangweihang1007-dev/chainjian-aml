from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GraphEdge:
    transaction_id: str
    source: str
    target: str
    timestamp: str
    amount: float
    currency: str
    evidence_type: str
    priority: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoleProfile:
    account_id: str
    roles: list[str]
    in_count: int
    out_count: int
    in_amount: float
    out_amount: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
