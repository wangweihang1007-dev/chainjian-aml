"""Persist versioned graph-intelligence results in the APP layer."""

from __future__ import annotations

import json
from core.database import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_graph_intelligence (
    alert_id TEXT PRIMARY KEY,
    computed_at TEXT NOT NULL,
    max_hops INTEGER NOT NULL,
    result_json TEXT NOT NULL
);
"""


def save_result(database_path: Path, alert_id: str, max_hops: int, result: dict[str, Any]) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("INSERT INTO app_graph_intelligence VALUES (?, ?, ?, ?) ON CONFLICT(alert_id) DO UPDATE SET computed_at=excluded.computed_at, max_hops=excluded.max_hops, result_json=excluded.result_json", (alert_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), max_hops, json.dumps(result, ensure_ascii=False)))


def load_result(database_path: Path, alert_id: str, max_hops: int) -> dict[str, Any] | None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        row = connection.execute("SELECT result_json FROM app_graph_intelligence WHERE alert_id=? AND max_hops=?", (alert_id, max_hops)).fetchone()
    return json.loads(row[0]) if row else None
