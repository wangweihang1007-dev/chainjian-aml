"""Deterministic behavior rules extracted from the AML reference material.

The thresholds are internal demo defaults, not a statement of universal
regulatory limits. They are kept in code so each alert remains explainable and
can be tuned without changing the other graph rules.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


def _make_alert(code: str, account_id: str, rows: list[dict], evidence_type: str, explanation: str, details: dict, score: float) -> Alert:
    transaction_ids = [str(row["transaction_id"]) for row in rows]
    fingerprint = hashlib.sha256(f"{code}|{account_id}|{'|'.join(sorted(transaction_ids))}".encode()).hexdigest()[:16]
    evidence = Evidence(evidence_type, transaction_ids, [account_id, *[str(row["target_account_id"]) for row in rows]], details)
    return Alert(f"ALT-{code[:8]}-{fingerprint}", account_id, score, "medium", [RuleHit(code, 3, explanation)], [evidence], datetime.now().astimezone().isoformat(timespec="seconds"))


class DailyActivityRule:
    """Flag high daily turnover or a high-frequency/many-counterparty day."""

    code = "DAILY_ACTIVITY_ANOMALY"

    def __init__(self, warehouse_path: Path, daily_amount: float = 50_000, min_transfers: int = 8, min_recipients: int = 5, max_alerts: int = 100) -> None:
        self.warehouse_path = warehouse_path
        self.daily_amount = daily_amount
        self.min_transfers = min_transfers
        self.min_recipients = min_recipients
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for raw in run_read(TRANSFER_QUERY):
            raw["event_time"] = to_datetime(raw["timestamp"])
            grouped[(raw["source_account_id"], raw["event_time"].date().isoformat())].append(raw)
        alerts: list[Alert] = []
        for (account_id, day), rows in grouped.items():
            total = sum(float(row["amount_paid"] or 0) for row in rows)
            recipients = len({row["target_account_id"] for row in rows})
            frequency_pattern = len(rows) >= self.min_transfers and recipients >= self.min_recipients
            if total < self.daily_amount and not frequency_pattern:
                continue
            reason = f"{day}: daily outgoing total {total:.2f}"
            if frequency_pattern:
                reason += f", {len(rows)} transfers to {recipients} recipients"
            alerts.append(_make_alert(self.code, account_id, rows, "daily_activity", reason, {
                "date": day, "daily_amount": round(total, 2), "transfer_count": len(rows), "distinct_recipients": recipients,
                "threshold_amount": self.daily_amount, "threshold_transfer_count": self.min_transfers, "threshold_recipients": self.min_recipients,
            }, 25.0))
            if len(alerts) >= self.max_alerts:
                break
        return alerts


class NearThresholdStructuringRule:
    """Flag repeated transfers near the documented 1,000-unit demo baseline."""

    code = "NEAR_THRESHOLD_STRUCTURING"

    def __init__(self, warehouse_path: Path, baseline: float = 1_000, tolerance: float = 100, window_hours: int = 3, min_transfers: int = 3, max_alerts: int = 100) -> None:
        self.warehouse_path = warehouse_path
        self.baseline = baseline
        self.tolerance = tolerance
        self.window = timedelta(hours=window_hours)
        self.min_transfers = min_transfers
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        lower, upper = self.baseline - self.tolerance, self.baseline + self.tolerance
        for raw in run_read(TRANSFER_QUERY):
            if lower <= float(raw["amount_paid"] or 0) <= upper:
                raw["event_time"] = to_datetime(raw["timestamp"])
                grouped[raw["source_account_id"]].append(raw)
        alerts: list[Alert] = []
        for account_id, rows in grouped.items():
            rows.sort(key=lambda item: item["event_time"])
            for index, first in enumerate(rows):
                window_rows = [candidate for candidate in rows[index:] if candidate["event_time"] - first["event_time"] <= self.window]
                recipients = len({row["target_account_id"] for row in window_rows})
                if len(window_rows) < self.min_transfers or recipients < self.min_transfers:
                    continue
                alerts.append(_make_alert(self.code, account_id, window_rows, "near_threshold_structuring",
                    f"{len(window_rows)} transfers near {self.baseline:.0f} within {self.window.total_seconds() / 3600:.0f} hours to {recipients} recipients.", {
                        "baseline": self.baseline, "tolerance": self.tolerance, "window_hours": self.window.total_seconds() / 3600,
                        "transfer_count": len(window_rows), "distinct_recipients": recipients,
                    }, 30.0))
                break
            if len(alerts) >= self.max_alerts:
                break
        return alerts
