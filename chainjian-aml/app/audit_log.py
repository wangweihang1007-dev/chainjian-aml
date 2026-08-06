"""Append-only audit logging for reviewer actions."""

from __future__ import annotations

from core.database import sqlite3

from app.review_model import AuditLog


def next_log_id(connection: sqlite3.Connection) -> str:
    latest = connection.execute("SELECT log_id FROM audit_log ORDER BY log_id DESC LIMIT 1").fetchone()
    return f"LG{(int(latest[0][2:]) + 1) if latest else 1:06d}"


def write_audit_log(
    connection: sqlite3.Connection, alert_id: str, operation: str, operator: str, timestamp: str, detail: str
) -> AuditLog:
    entry = AuditLog(next_log_id(connection), alert_id, operation, operator, timestamp, detail)
    connection.execute(
        "INSERT INTO audit_log (log_id, alert_id, operation, operator, timestamp, detail) VALUES (?, ?, ?, ?, ?, ?)",
        (entry.log_id, entry.alert_id, entry.operation, entry.operator, entry.timestamp, entry.detail),
    )
    return entry
