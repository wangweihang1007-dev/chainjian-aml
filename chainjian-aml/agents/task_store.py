"""SQLite persistence for auditable multi-agent investigation tasks."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS investigation_task (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_summary TEXT,
    status TEXT NOT NULL CHECK (status IN ('WAITING','RUNNING','COMPLETED','FAILED')),
    created_time TEXT NOT NULL,
    started_time TEXT,
    finished_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_investigation_task_alert ON investigation_task(alert_id, task_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summary(value: Any) -> str:
    if isinstance(value, dict):
        compact = {key: value[key] for key in ("rule_hits", "risk_level", "risk_score", "paths", "suspicious_nodes", "risk_points", "recommendations", "reason", "advisory_only") if key in value}
        return json.dumps(compact or {"keys": list(value)[:20]}, ensure_ascii=False, default=str)[:4000]
    if isinstance(value, list):
        return json.dumps({"count": len(value), "sample": value[:3]}, ensure_ascii=False, default=str)[:4000]
    return str(value)[:4000]


class InvestigationTaskStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self, alert_id: str, tasks: list[dict[str, Any]]) -> dict[str, int]:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(SCHEMA)
            ids = {}
            for task in tasks:
                cursor = connection.execute(
                    """INSERT INTO investigation_task
                    (alert_id, agent_name, task_type, input_json, status, created_time)
                    VALUES (?, ?, ?, ?, 'WAITING', ?)""",
                    (alert_id, task["agent_name"], task["task_type"], json.dumps(task.get("input", {}), ensure_ascii=False), _now()),
                )
                ids[task["task_id"]] = int(cursor.lastrowid)
            connection.commit()
            return ids
        finally:
            connection.close()

    def start(self, task_id: int) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE investigation_task SET status='RUNNING', started_time=? WHERE task_id=?", (_now(), task_id))
            connection.commit()
        finally:
            connection.close()

    def finish(self, task_id: int, status: str, output: Any) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("UPDATE investigation_task SET status=?, output_summary=?, finished_time=? WHERE task_id=?", (status, _summary(output), _now(), task_id))
            connection.commit()
        finally:
            connection.close()

    def list(self, alert_id: str) -> list[dict[str, Any]]:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(SCHEMA)
            rows = connection.execute("""SELECT task_id, agent_name, task_type, input_json, output_summary,
                status, created_time, started_time, finished_time FROM investigation_task
                WHERE alert_id=? ORDER BY task_id""", (alert_id,)).fetchall()
        finally:
            connection.close()
        return [{"task_id": row[0], "agent_name": row[1], "task_type": row[2], "input": json.loads(row[3]), "output_summary": row[4], "status": row[5], "created_time": row[6], "started_time": row[7], "finished_time": row[8]} for row in rows]
