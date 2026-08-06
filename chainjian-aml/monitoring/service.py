"""Compute and persist launch monitoring metrics from the warehouse."""

from __future__ import annotations

import json
from core.database import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.neo4j_client import run_read
from core.warehouse import DEFAULT_DATABASE
from evaluation.evaluate_rules import evaluate_rules

MONITORING_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitoring_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_monitoring_snapshot_time ON monitoring_snapshot(snapshot_at);
"""


def psi(expected: list[float], actual: list[float], bins: int = 10) -> float:
    """Calculate PSI using equal-width bins; zero counts are smoothed."""
    if not expected or not actual:
        return 0.0
    low, high = min(expected + actual), max(expected + actual)
    if low == high:
        return 0.0
    width = (high - low) / bins
    def distribution(values: list[float]) -> list[float]:
        counts = [0] * bins
        for value in values:
            index = min(bins - 1, int((value - low) / width))
            counts[index] += 1
        total = max(sum(counts), 1)
        return [max(count / total, 1e-6) for count in counts]
    base, current = distribution(expected), distribution(actual)
    return round(sum((cur - ref) * __import__("math").log(cur / ref) for ref, cur in zip(base, current)), 6)


def level(value: float, yellow: float, red: float) -> str:
    return "RED" if value >= red else ("YELLOW" if value >= yellow else "GREEN")


def collect_metrics(database_path: Path = DEFAULT_DATABASE, include_graph: bool = True, quality_mode: str = "balanced") -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with sqlite3.connect(database_path) as connection:
        connection.executescript(MONITORING_SCHEMA)
        transaction_rows = connection.execute("SELECT amount_paid, amount_received, transaction_time, from_account_id, to_account_id FROM dwd_transaction_detail").fetchall()
        score_rows = connection.execute("SELECT risk_score FROM alert_case").fetchall()
        alert_rows = connection.execute("SELECT rule_hits_json, status, risk_level FROM alert_case").fetchall()
        reviews = connection.execute("SELECT action FROM review_record").fetchall()
        sync = connection.execute("SELECT created_at, status, new_rows, sqlite_inserted, neo4j_synced, error FROM realtime_sync_run ORDER BY created_at DESC LIMIT 1").fetchone() if _table_exists(connection, "realtime_sync_run") else None
        missing = connection.execute("""SELECT SUM(CASE WHEN transaction_id IS NULL OR transaction_time IS NULL OR from_account_id IS NULL OR to_account_id IS NULL OR amount_paid IS NULL OR payment_currency IS NULL THEN 1 ELSE 0 END), count(*) FROM dwd_transaction_detail""").fetchone()
        duplicate_count = connection.execute("SELECT count(*) - count(DISTINCT transaction_id) FROM dwd_transaction_detail").fetchone()[0]
        rule_counts: Counter[str] = Counter()
        for serialized, _, _ in alert_rows:
            rule_counts.update(json.loads(serialized))
        metrics = {
            "snapshot_at": now,
            "data_quality": {
                "transaction_count": len(transaction_rows),
                "missing_field_rate": round((missing[0] or 0) / max(missing[1] or 1, 1), 6),
                "duplicate_transaction_count": duplicate_count,
                "status": "RED" if (missing[0] or 0) > 0 or duplicate_count > 0 else "GREEN",
            },
            "distribution": {
                "amount_p10": _percentile([float(row[0]) for row in transaction_rows], 0.10),
                "amount_p90": _percentile([float(row[0]) for row in transaction_rows], 0.90),
                "amount_p99": _percentile([float(row[0]) for row in transaction_rows], 0.99),
                "risk_score_psi": 0.0,
            },
            "rules": {"hit_counts": dict(rule_counts), "total_alert_cases": len(alert_rows)},
            "review": {
                "pending_count": sum(1 for _, status, _ in alert_rows if status == "PENDING"),
                "confirmed_count": sum(1 for action, in reviews if action == "CONFIRM"),
                "rejected_count": sum(1 for action, in reviews if action == "REJECT"),
                "review_count": len(reviews),
            },
            "realtime_sync": dict(zip(("created_at", "status", "new_rows", "sqlite_inserted", "neo4j_synced", "error"), sync)) if sync else None,
        }
        metrics["evaluation"] = evaluate_rules(database_path, quality_mode=quality_mode)
        scores = [float(row[0]) for row in score_rows]
        metrics["distribution"]["risk_score_psi_level"] = level(metrics["distribution"]["risk_score_psi"], 0.10, 0.25)
        if include_graph:
            try:
                graph = run_read("MATCH (a:Account) OPTIONAL MATCH ()-[t:TRANSFER]->() RETURN count(DISTINCT a) AS nodes, count(DISTINCT t) AS edges")
                metrics["graph"] = {**(graph[0] if graph else {"nodes": 0, "edges": 0}), "status": "GREEN"}
            except Exception as error:
                metrics["graph"] = {"nodes": None, "edges": None, "status": "RED", "error": str(error)}
        connection.execute("INSERT INTO monitoring_snapshot (snapshot_at, payload_json) VALUES (?, ?)", (now, json.dumps(metrics, ensure_ascii=False)))
    return metrics


def latest_snapshot(database_path: Path = DEFAULT_DATABASE) -> dict[str, Any] | None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(MONITORING_SCHEMA)
        row = connection.execute("SELECT payload_json FROM monitoring_snapshot ORDER BY snapshot_id DESC LIMIT 1").fetchone()
    return json.loads(row[0]) if row else None


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))], 2)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())
