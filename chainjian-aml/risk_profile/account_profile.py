"""Serializable account risk profile model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class AccountRiskProfile:
    account_id: str
    account_age_days: int | None
    txn_count: int
    total_amount: float
    inflow_amount: float
    outflow_amount: float
    counterparty_count: int
    associated_account_count: int
    average_transaction_amount: float
    maximum_transaction_amount: float
    average_holding_time_minutes: float | None
    anomalous_transaction_count: int
    active_days: int | None
    risk_features: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
