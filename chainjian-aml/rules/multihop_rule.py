"""Detect time-ordered transfer chains longer than three hops."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


class MultiHopRule:
    code = "MULTI_HOP_TRANSFER"
    severity = 3

    def __init__(self, warehouse_path: Path, hops: int = 4, window_hours: int = 72, max_amount_change_ratio: float = 0.35, max_alerts: int = 50) -> None:
        self.warehouse_path = warehouse_path
        self.hops = hops
        self.window = timedelta(hours=window_hours)
        self.max_amount_change_ratio = max_amount_change_ratio
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in run_read(TRANSFER_QUERY):
            row["event_time"] = to_datetime(row["timestamp"])
            adjacency[row["source_account_id"]].append(row)
        for rows in adjacency.values():
            rows.sort(key=lambda item: item["event_time"])
        alerts: list[Alert] = []
        seen: set[str] = set()
        for start in sorted(adjacency):
            self._walk(start, start, [], {start}, adjacency, alerts, seen)
            if len(alerts) >= self.max_alerts:
                break
        return alerts

    def _walk(self, start: str, current: str, path: list[dict], visited: set[str], adjacency: dict[str, list[dict]], alerts: list[Alert], seen: set[str]) -> None:
        if len(alerts) >= self.max_alerts:
            return
        if len(path) == self.hops:
            alert = self._alert(start, path)
            if alert.alert_id not in seen:
                seen.add(alert.alert_id)
                alerts.append(alert)
            return
        for edge in adjacency.get(current, []):
            if edge["target_account_id"] in visited:
                continue
            if path and (edge["event_time"] < path[-1]["event_time"] or edge["event_time"] - path[0]["event_time"] > self.window):
                continue
            if path:
                previous, amount = float(path[-1]["amount_paid"]), float(edge["amount_paid"])
                if abs(previous - amount) / max(previous, amount) > self.max_amount_change_ratio:
                    continue
            self._walk(start, edge["target_account_id"], [*path, edge], visited | {edge["target_account_id"]}, adjacency, alerts, seen)
            if len(alerts) >= self.max_alerts:
                return

    def _alert(self, account_id: str, path: list[dict]) -> Alert:
        transaction_ids = [edge["transaction_id"] for edge in path]
        identifier = hashlib.sha256(f"{self.code}|{'|'.join(sorted(transaction_ids))}".encode()).hexdigest()[:16]
        evidence = Evidence("multi_hop_path", transaction_ids, [path[0]["source_account_id"], *[edge["target_account_id"] for edge in path]], {
            "hop_count": len(path), "duration_hours": round((path[-1]["event_time"] - path[0]["event_time"]).total_seconds() / 3600, 2),
            "amounts": [edge["amount_paid"] for edge in path],
        })
        return Alert(f"ALT-MULTI-{identifier}", account_id, 55.0, "medium", [RuleHit(self.code, self.severity, f"Detected a time-ordered {len(path)}-hop transfer chain.")], [evidence], datetime.now().astimezone().isoformat(timespec="seconds"))
