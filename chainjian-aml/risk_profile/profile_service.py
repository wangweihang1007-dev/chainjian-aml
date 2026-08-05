"""Build an explainable account profile from DWD transactions and DWS."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.warehouse import DEFAULT_DATABASE
from risk_profile.account_profile import AccountRiskProfile


def _parse_time(value: str) -> datetime:
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return datetime.strptime(text, "%Y/%m/%d %H:%M:%S")


class AccountProfileService:
    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def build(self, account_id: str) -> AccountRiskProfile:
        import sqlite3

        connection = sqlite3.connect(self.warehouse_path)
        try:
            rows = connection.execute(
                """SELECT transaction_id, transaction_time, from_account_id, to_account_id,
                          amount_paid, amount_received
                   FROM dwd_transaction_detail
                   WHERE from_account_id = ? OR to_account_id = ?
                   ORDER BY transaction_time, transaction_id""",
                (account_id, account_id),
            ).fetchall()
            feature_row = connection.execute(
                """SELECT total_transaction_count, outbound_amount, inbound_amount,
                          counterparty_count
                   FROM dws_account_risk_features WHERE account_id = ?""",
                (account_id,),
            ).fetchone()
            account_row = connection.execute(
                "SELECT effective_batch_id FROM dim_account WHERE account_id = ?", (account_id,)
            ).fetchone()
        finally:
            connection.close()

        inflows = [row for row in rows if row[3] == account_id and row[2] != account_id]
        outflows = [row for row in rows if row[2] == account_id and row[3] != account_id]
        amounts = [float(row[4]) for row in outflows] + [float(row[5]) for row in inflows]
        counterparties = {row[2] if row[3] == account_id else row[3] for row in rows if row[2] != row[3]}
        holding_times: list[float] = []
        used_outflows: set[str] = set()
        for incoming in inflows:
            incoming_time = _parse_time(incoming[1])
            candidates = [
                outgoing for outgoing in outflows
                if outgoing[0] not in used_outflows
                and _parse_time(outgoing[1]) >= incoming_time
                and _parse_time(outgoing[1]) - incoming_time <= timedelta(hours=24)
            ]
            if candidates:
                outgoing = candidates[0]
                used_outflows.add(outgoing[0])
                holding_times.append((_parse_time(outgoing[1]) - incoming_time).total_seconds() / 60)

        txn_count = len(rows)
        active_days = len({str(row[1])[:10] for row in rows}) if rows else 0
        inflow_amount = round(sum(float(row[5]) for row in inflows), 2)
        outflow_amount = round(sum(float(row[4]) for row in outflows), 2)
        total_amount = round(inflow_amount + outflow_amount, 2)
        average_amount = round(sum(amounts) / len(amounts), 2) if amounts else 0.0
        maximum_amount = round(max(amounts), 2) if amounts else 0.0
        anomalous = sum(1 for amount in amounts if average_amount and amount >= average_amount * 5)
        features: list[str] = []
        if txn_count >= 20:
            features.append("高频交易")
        if len(counterparties) >= 10:
            features.append("多账户关联")
        if outflow_amount >= 50_000:
            features.append("高额资金流出")
        if holding_times and sum(holding_times) / len(holding_times) <= 120:
            features.append("资金快进快出")
        if anomalous:
            features.append("异常金额")
        return AccountRiskProfile(
            account_id=account_id,
            account_age_days=None if account_row is None else None,
            txn_count=txn_count if feature_row is None else int(feature_row[0]),
            total_amount=total_amount,
            inflow_amount=inflow_amount if feature_row is None else round(float(feature_row[2]), 2),
            outflow_amount=outflow_amount if feature_row is None else round(float(feature_row[1]), 2),
            counterparty_count=len(counterparties) if feature_row is None else int(feature_row[3]),
            associated_account_count=len(counterparties),
            average_transaction_amount=average_amount,
            maximum_transaction_amount=maximum_amount,
            average_holding_time_minutes=round(sum(holding_times) / len(holding_times), 2) if holding_times else None,
            anomalous_transaction_count=anomalous,
            active_days=active_days,
            risk_features=features,
        )

    def get(self, account_id: str) -> dict:
        return self.build(account_id).as_dict()
