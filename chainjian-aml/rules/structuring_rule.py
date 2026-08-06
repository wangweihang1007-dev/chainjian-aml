"""Detect short-window split transfers from a source account."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit
from core.neo4j_client import run_read


class StructuringRule:
    code = "STRUCTURING_TRANSFER"
    severity = 4

    def __init__(self, warehouse_path: Path, window_hours: int = 6, small_amount: float = 15000, min_amount: float = 1500, min_transfers: int = 5, max_alerts: int = 50) -> None:
        self.warehouse_path = warehouse_path
        self.window = timedelta(hours=window_hours)
        self.small_amount = small_amount
        self.min_amount = min_amount
        self.min_transfers = min_transfers
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        by_source = defaultdict(list)
        for row in run_read(TRANSFER_QUERY):
            if self.min_amount <= float(row["amount_paid"]) <= self.small_amount:
                row["event_time"] = to_datetime(row["timestamp"])
                by_source[row["source_account_id"]].append(row)
        alerts = []
        for account_id, rows in by_source.items():
            rows.sort(key=lambda item: item["event_time"])
            for index, row in enumerate(rows):
                window_rows = [candidate for candidate in rows[index:] if candidate["event_time"] - row["event_time"] <= self.window]
                if len(window_rows) >= self.min_transfers and len({candidate["target_account_id"] for candidate in window_rows}) >= self.min_transfers:
                    alerts.append(self._alert(account_id, window_rows))
                    break
            if len(alerts) >= self.max_alerts:
                break
        return alerts

    def _alert(self, account_id: str, rows: list[dict]) -> Alert:
        transaction_ids = [row["transaction_id"] for row in rows]
        identifier = hashlib.sha256(f"{self.code}|{account_id}|{'|'.join(sorted(transaction_ids))}".encode()).hexdigest()[:16]
        evidence = Evidence("split_transfer", transaction_ids, [account_id, *[row["target_account_id"] for row in rows]], {
            "window_hours": self.window.total_seconds() / 3600, "transfer_count": len(rows),
            "min_amount": self.min_amount, "max_amount": self.small_amount,
            "distinct_recipients": len({row["target_account_id"] for row in rows}), "amounts": [row["amount_paid"] for row in rows],
        })
        return Alert(f"ALT-STRUCT-{identifier}", account_id, 70.0, "medium", [RuleHit(self.code, self.severity, f"Detected {len(rows)} small transfers to multiple recipients within {self.window.total_seconds() / 3600:.0f} hours.")], [evidence], datetime.now().astimezone().isoformat(timespec="seconds"))
