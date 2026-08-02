"""Detect funds entering an account and mostly leaving shortly afterwards."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


class RapidMovementRule:
    code = "RAPID_MOVEMENT"
    severity = 3

    def __init__(self, warehouse_path: Path, window_hours: int = 2, min_incoming_amount: float = 5_000, min_outflow_ratio: float = 0.8, max_alerts: int = 100) -> None:
        self.warehouse_path = warehouse_path
        self.window = timedelta(hours=window_hours)
        self.min_incoming_amount = min_incoming_amount
        self.min_outflow_ratio = min_outflow_ratio
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        incoming: dict[str, list[dict]] = defaultdict(list)
        outgoing: dict[str, list[dict]] = defaultdict(list)
        for raw in run_read(TRANSFER_QUERY):
            raw["event_time"] = to_datetime(raw["timestamp"])
            if raw["source_account_id"] != raw["target_account_id"]:
                if float(raw["amount_paid"] or 0) >= self.min_incoming_amount:
                    incoming[raw["target_account_id"]].append(raw)
                outgoing[raw["source_account_id"]].append(raw)
        alerts: list[Alert] = []
        for account_id, in_rows in incoming.items():
            for in_row in sorted(in_rows, key=lambda item: item["event_time"]):
                candidates = [
                    out_row for out_row in outgoing.get(account_id, [])
                    if out_row["event_time"] >= in_row["event_time"]
                    and out_row["event_time"] - in_row["event_time"] <= self.window
                ]
                if not candidates:
                    continue
                out_row = min(candidates, key=lambda item: item["event_time"])
                incoming_amount = float(in_row["amount_paid"] or 0)
                outgoing_amount = float(out_row["amount_paid"] or 0)
                if outgoing_amount < incoming_amount * self.min_outflow_ratio:
                    continue
                minutes = round((out_row["event_time"] - in_row["event_time"]).total_seconds() / 60, 2)
                transaction_ids = [in_row["transaction_id"], out_row["transaction_id"]]
                fingerprint = hashlib.sha256(f"{self.code}|{account_id}|{'|'.join(transaction_ids)}".encode()).hexdigest()[:16]
                evidence = Evidence("rapid_movement", transaction_ids, [in_row["source_account_id"], account_id, out_row["target_account_id"]], {
                    "in_transaction": in_row["transaction_id"], "out_transaction": out_row["transaction_id"],
                    "holding_time_minutes": minutes, "incoming_amount": incoming_amount, "outgoing_amount": outgoing_amount,
                    "outflow_ratio": round(outgoing_amount / incoming_amount, 4), "window_hours": self.window.total_seconds() / 3600,
                })
                alerts.append(Alert(f"ALT-RAPID-{fingerprint}", account_id, 30.0, "medium", [RuleHit(self.code, self.severity, f"{outgoing_amount:.2f} left the account {minutes:.0f} minutes after an incoming transfer.")], [evidence], datetime.now().astimezone().isoformat(timespec="seconds")))
                break
            if len(alerts) >= self.max_alerts:
                break
        return alerts
