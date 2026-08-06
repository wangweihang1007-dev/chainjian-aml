"""Auditable investigation step trace persistence."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.database import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS investigation_trace (
    trace_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('WAITING','RUNNING','COMPLETED','FAILED')),
    tool_name TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_summary TEXT,
    started_time TEXT,
    finished_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_investigation_trace_alert ON investigation_trace(alert_id, trace_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class InvestigationTraceStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self, alert_id: str, steps: list[dict[str, Any]]) -> dict[str, int]:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(SCHEMA)
            result: dict[str, int] = {}
            for step in steps:
                cursor = connection.execute("INSERT INTO investigation_trace (alert_id, step_id, step_name, status, tool_name, input_json) VALUES (?, ?, ?, 'WAITING', ?, ?)", (alert_id, step["step_id"], step["step_name"], step["tool_name"], json.dumps(step.get("input", {}), ensure_ascii=False)))
                result[step["step_id"]] = int(cursor.lastrowid)
            connection.commit()
            return result
        finally:
            connection.close()

    def start(self, trace_id: int) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE investigation_trace SET status='RUNNING', started_time=? WHERE trace_id=?", (_now(), trace_id))
            connection.commit()
        finally:
            connection.close()

    def finish(self, trace_id: int, status: str, output: Any = None) -> None:
        summary = _summarize(output)
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE investigation_trace SET status=?, output_summary=?, finished_time=? WHERE trace_id=?", (status, summary, _now(), trace_id))
            connection.commit()
        finally:
            connection.close()

    def list(self, alert_id: str) -> list[dict[str, Any]]:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(SCHEMA)
            rows = connection.execute("SELECT step_id, step_name, status, tool_name, input_json, output_summary, started_time, finished_time FROM investigation_trace WHERE alert_id=? ORDER BY trace_id", (alert_id,)).fetchall()
        finally:
            connection.close()
        return [{"step_id": row[0], "step_name": row[1], "status": row[2], "tool_name": row[3], "input": json.loads(row[4]), "output_summary": row[5], "started_time": row[6], "finished_time": row[7]} for row in rows]


def _summarize(value: Any) -> str:
    if isinstance(value, dict):
        compact = {key: value[key] for key in ("alert_id", "account_id", "risk_level", "risk_score", "rule_hits", "holding_time_minutes", "recommendations", "reason", "advisory_only") if key in value}
        if compact:
            return json.dumps(compact, ensure_ascii=False)
        return json.dumps({"keys": list(value.keys())[:20]}, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps({"count": len(value), "sample": value[:3]}, ensure_ascii=False, default=str)
    return str(value)[:1000]
