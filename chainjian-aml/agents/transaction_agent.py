"""DWD/DWS transaction behavior investigation agent."""

from __future__ import annotations

from core.database import sqlite3
from pathlib import Path
from typing import Any

from core.warehouse import DEFAULT_DATABASE
from risk_profile.profile_service import AccountProfileService
from rules.rapid_movement_rule import RapidMovementRule


class TransactionAgent:
    name = "Transaction Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def run(self, account_id: str) -> dict[str, Any]:
        profile = AccountProfileService(self.warehouse_path).get(account_id)
        rapid = [item.as_dict() for item in RapidMovementRule(self.warehouse_path).detect() if item.account_id == account_id]
        with sqlite3.connect(self.warehouse_path) as connection:
            rows = connection.execute("""SELECT transaction_id, transaction_time, amount_paid, amount_received,
                from_account_id, to_account_id FROM dwd_transaction_detail
                WHERE from_account_id=? OR to_account_id=? ORDER BY transaction_time""", (account_id, account_id)).fetchall()
        large = [row[0] for row in rows if float(row[2] or 0) >= 50000 or float(row[3] or 0) >= 50000]
        risk_points = []
        if "高频交易" in profile.get("risk_features", []):
            risk_points.append("高频交易")
        if large:
            risk_points.append("大额交易")
        if rapid:
            risk_points.append("快进快出")
        return {"account_id": account_id, "features": profile, "risk_points": risk_points, "rapid_movement": rapid, "transaction_count": len(rows), "key_transaction_ids": [row[0] for row in rows[:20]], "large_transaction_ids": large[:20]}
