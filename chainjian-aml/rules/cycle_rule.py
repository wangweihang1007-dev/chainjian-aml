"""Circular fund-flow detection using Neo4j transfer data."""

from __future__ import annotations

import hashlib
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.neo4j_client import run_read

from rules.models import Alert, Evidence, RuleHit


TRANSFER_QUERY = """
MATCH (source:Account)-[transfer:TRANSFER]->(target:Account)
RETURN source.account_id AS source_account_id,
       target.account_id AS target_account_id,
       transfer.transaction_id AS transaction_id,
       transfer.timestamp AS timestamp,
       transfer.amount_paid AS amount_paid,
       transfer.payment_currency AS payment_currency
ORDER BY transfer.timestamp, transfer.transaction_id
"""


def to_datetime(value: Any) -> datetime:
    """Normalize Neo4j temporal values and ISO strings to naive datetimes."""
    if hasattr(value, "to_native"):
        value = value.to_native()
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return datetime.strptime(text, "%Y/%m/%d %H:%M:%S").replace(tzinfo=None)


class CycleRule:
    code = "CYCLE_TRANSFER"
    severity = 5

    def __init__(
        self,
        warehouse_path: Path,
        min_hops: int = 3,
        max_hops: int = 8,
        window_hours: int = 96,
        max_amount_change_ratio: float = 0.35,
        max_alerts: int = 100,
    ) -> None:
        self.warehouse_path = warehouse_path
        self.min_hops = min_hops
        self.max_hops = max_hops
        self.window = timedelta(hours=window_hours)
        self.max_amount_change_ratio = max_amount_change_ratio
        self.max_alerts = max_alerts

    def detect(self) -> list[Alert]:
        """Return canonical, time-bounded simple cycles from the Neo4j graph."""
        edges = [
            {**row, "event_time": to_datetime(row["timestamp"])}
            for row in run_read(TRANSFER_QUERY)
            if row["source_account_id"] != row["target_account_id"]
        ]
        features = self._load_features()
        adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for edge in edges:
            adjacency[edge["source_account_id"]].append(edge)
        for account_edges in adjacency.values():
            account_edges.sort(key=lambda item: (item["event_time"], item["transaction_id"]))

        alerts: list[Alert] = []
        for start_account in sorted(adjacency):
            self._search(
                start=start_account,
                current=start_account,
                path=[],
                visited={start_account},
                adjacency=adjacency,
                features=features,
                alerts=alerts,
            )
            if len(alerts) >= self.max_alerts:
                break
        # Starting from the earliest transfer is necessary for temporal order,
        # so cycle identity is deduplicated by its stable transaction-based ID
        # instead of by a lexical account-id start node.
        return list({alert.alert_id: alert for alert in alerts}.values())

    def _search(
        self,
        start: str,
        current: str,
        path: list[dict[str, Any]],
        visited: set[str],
        adjacency: dict[str, list[dict[str, Any]]],
        features: dict[str, dict[str, int | float]],
        alerts: list[Alert],
    ) -> None:
        if len(alerts) >= self.max_alerts or len(path) >= self.max_hops:
            return
        for edge in adjacency.get(current, []):
            if path and edge["event_time"] < path[-1]["event_time"]:
                continue
            if path and edge["event_time"] - path[0]["event_time"] > self.window:
                continue
            if path and not self._amounts_are_continuous(path[-1], edge):
                continue
            target = edge["target_account_id"]
            candidate = [*path, edge]
            if target == start:
                if len(candidate) >= self.min_hops:
                    alerts.append(self._make_alert(candidate, features))
                continue
            if target in visited:
                continue
            self._search(start, target, candidate, visited | {target}, adjacency, features, alerts)
            if len(alerts) >= self.max_alerts:
                return

    def _amounts_are_continuous(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        """Reject branch edges whose amounts break the apparent fund flow."""
        previous_amount = float(previous["amount_paid"])
        current_amount = float(current["amount_paid"])
        change_ratio = abs(current_amount - previous_amount) / max(previous_amount, current_amount)
        return change_ratio <= self.max_amount_change_ratio

    def _make_alert(self, path: list[dict[str, Any]], features: dict[str, dict[str, int | float]]) -> Alert:
        account_path = [path[0]["source_account_id"], *[edge["target_account_id"] for edge in path]]
        transaction_ids = [edge["transaction_id"] for edge in path]
        anchor_account = account_path[0]
        feature = features.get(anchor_account, {})
        hops = len(path)
        # A circular path is intrinsically high risk; DWS transaction breadth
        # is used only to prioritize within the high-risk band.
        score = min(100.0, 80.0 + hops * 1.5 + min(float(feature.get("counterparty_count", 0)), 8.0) * 0.5)
        alert_hash = hashlib.sha256(f"{self.code}|{'|'.join(sorted(transaction_ids))}".encode()).hexdigest()[:16]
        start_time, end_time = path[0]["event_time"], path[-1]["event_time"]
        evidence = Evidence(
            evidence_type="circular_fund_flow",
            transaction_ids=transaction_ids,
            account_path=account_path,
            details={
                "hop_count": hops,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_hours": round((end_time - start_time).total_seconds() / 3600, 2),
                "amounts": [edge["amount_paid"] for edge in path],
                "currencies": [edge["payment_currency"] for edge in path],
            },
        )
        return Alert(
            alert_id=f"ALT-CYCLE-{alert_hash}",
            account_id=anchor_account,
            risk_score=round(score, 2),
            risk_level="high",
            rule_hits=[RuleHit(self.code, self.severity, f"Detected a {hops}-hop circular transfer path within {self.window.total_seconds() / 3600:.0f} hours.")],
            evidence=[evidence],
            created_time=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def _load_features(self) -> dict[str, dict[str, int | float]]:
        with sqlite3.connect(self.warehouse_path) as connection:
            rows = connection.execute(
                "SELECT account_id, total_transaction_count, counterparty_count FROM dws_account_risk_features"
            ).fetchall()
        return {account_id: {"total_transaction_count": transactions, "counterparty_count": counterparties} for account_id, transactions, counterparties in rows}
