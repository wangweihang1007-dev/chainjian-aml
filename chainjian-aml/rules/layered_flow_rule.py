"""Detect layered scatter/gather money-flow topologies."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY, to_datetime
from rules.models import Alert, Evidence, RuleHit


class LayeredFlowRule:
    """Find a high-degree two-layer flow rather than isolated fan behavior."""

    code = "LAYERED_FLOW"
    severity = 4

    def __init__(self, warehouse_path: Path, window_hours: int = 96, min_branches: int = 5, max_alerts: int = 50, include_gather: bool = False) -> None:
        self.warehouse_path = warehouse_path
        self.window = timedelta(hours=window_hours)
        self.min_branches = min_branches
        self.max_alerts = max_alerts
        self.include_gather = include_gather

    def detect(self) -> list[Alert]:
        rows = []
        for raw in run_read(TRANSFER_QUERY):
            row = dict(raw)
            row["event_time"] = to_datetime(row["timestamp"])
            rows.append(row)
        outgoing = defaultdict(list)
        incoming = defaultdict(list)
        for row in rows:
            outgoing[row["source_account_id"]].append(row)
            incoming[row["target_account_id"]].append(row)
        alerts = []
        seen = set()
        # Scatter -> gather: one source fans out, then the intermediates converge.
        for source, first_hop in outgoing.items():
            for target, second_hop in incoming.items():
                by_mid = {row["source_account_id"]: row for row in second_hop}
                mids = {row["target_account_id"] for row in first_hop} & set(by_mid)
                selected = [row for row in first_hop if row["target_account_id"] in mids]
                selected = [row for row in selected if by_mid[row["target_account_id"]]["event_time"] >= row["event_time"] and by_mid[row["target_account_id"]]["event_time"] - row["event_time"] <= self.window]
                if len(selected) >= self.min_branches:
                    edges = selected + [by_mid[row["target_account_id"]] for row in selected]
                    alert = self._alert(source, target, edges, "scatter_gather")
                    if alert.alert_id not in seen:
                        alerts.append(alert); seen.add(alert.alert_id)
        # Gather -> scatter is noisier on this corpus, so keep it opt-in.
        if self.include_gather:
          for middle, first_hop in incoming.items():
              targets = defaultdict(list)
              for row in outgoing.get(middle, []):
                  targets[row["target_account_id"]].append(row)
              if len(first_hop) < self.min_branches or len(targets) < self.min_branches:
                  continue
              earliest = min(row["event_time"] for row in first_hop)
              latest = max(row["event_time"] for row in first_hop)
              second = [row for values in targets.values() for row in values if row["event_time"] >= earliest and row["event_time"] - latest <= self.window]
              if len({row["target_account_id"] for row in second}) >= self.min_branches:
                  edges = first_hop + second
                  alert = self._alert(middle, middle, edges, "gather_scatter")
                  if alert.alert_id not in seen:
                      alerts.append(alert); seen.add(alert.alert_id)
        return alerts[: self.max_alerts]

    def _alert(self, account_id: str, target: str, rows: list[dict], kind: str) -> Alert:
        transaction_ids = sorted({str(row["transaction_id"]) for row in rows})
        fingerprint = hashlib.sha256(f"{self.code}|{kind}|{'|'.join(transaction_ids)}".encode()).hexdigest()[:16]
        evidence = Evidence(kind, transaction_ids, [account_id, target], {
            "window_hours": self.window.total_seconds() / 3600,
            "branch_count": len(transaction_ids),
            "min_branches": self.min_branches,
        })
        return Alert(f"ALT-LAYERED-{fingerprint}", account_id, 75.0, "high", [RuleHit(self.code, self.severity, f"Detected layered {kind.replace('_', ' ')} flow with at least {self.min_branches} branches.")], [evidence], datetime.now().astimezone().isoformat(timespec="seconds"))
