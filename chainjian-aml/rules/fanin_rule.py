"""Detect short-window multi-source fund collection."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


class FanInRule:
    code = "FAN_IN_COLLECTION"
    severity = 4

    def __init__(self, warehouse_path: Path, window_hours: int = 48, min_sources: int = 4, max_alerts: int = 50) -> None:
        self.warehouse_path = warehouse_path
        self.window = timedelta(hours=window_hours)
        self.min_sources = min_sources
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        by_target = defaultdict(list)
        for row in run_read(TRANSFER_QUERY):
            row["event_time"] = to_datetime(row["timestamp"])
            by_target[row["target_account_id"]].append(row)
        alerts = []
        for account_id, rows in by_target.items():
            rows.sort(key=lambda item: item["event_time"])
            for index, row in enumerate(rows):
                window_rows = [candidate for candidate in rows[index:] if candidate["event_time"] - row["event_time"] <= self.window]
                if len({candidate["source_account_id"] for candidate in window_rows}) >= self.min_sources:
                    alerts.append(self._alert(account_id, window_rows))
                    break
            if len(alerts) >= self.max_alerts:
                break
        return alerts

    def _alert(self, account_id: str, rows: list[dict]) -> Alert:
        transaction_ids = [row["transaction_id"] for row in rows]
        identifier = hashlib.sha256(f"{self.code}|{account_id}|{'|'.join(sorted(transaction_ids))}".encode()).hexdigest()[:16]
        evidence = Evidence("fan_in_collection", transaction_ids, [*[row["source_account_id"] for row in rows], account_id], {
            "window_hours": self.window.total_seconds() / 3600, "source_count": len({row["source_account_id"] for row in rows}),
            "transfer_count": len(rows), "total_amount": round(sum(float(row["amount_paid"]) for row in rows), 2),
        })
        return Alert(f"ALT-FANIN-{identifier}", account_id, 65.0, "medium", [RuleHit(self.code, self.severity, f"Detected funds from {len({row['source_account_id'] for row in rows})} source accounts within {self.window.total_seconds() / 3600:.0f} hours.")], [evidence], datetime.now().astimezone().isoformat(timespec="seconds"))
