"""Human review workflow with alert-state transitions and complete audit trail."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.alert_model import AlertCase
from app.alert_service import AlertService
from app.audit_log import write_audit_log
from app.review_model import AuditLog, ReviewRecord


REVIEW_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_record (
    review_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    reviewer TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('CONFIRM', 'REJECT', 'NEED_MORE_INFO')),
    comment TEXT NOT NULL,
    created_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    operation TEXT NOT NULL,
    operator TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_alert_time ON review_record(alert_id, created_time);
CREATE INDEX IF NOT EXISTS idx_audit_alert_time ON audit_log(alert_id, timestamp);
"""


class ReviewService:
    def __init__(self, warehouse_path: Path) -> None:
        self.warehouse_path = warehouse_path

    def pending_alerts(self) -> list[AlertCase]:
        alerts = AlertService(self.warehouse_path).list_alerts()
        return [alert for alert in alerts if alert.status == "PENDING"]

    def submit_review(self, alert_id: str, reviewer: str, action: str, comment: str = "") -> ReviewRecord:
        action = action.upper()
        reviewer, comment = reviewer.strip(), comment.strip()
        if action not in {"CONFIRM", "REJECT", "NEED_MORE_INFO"}:
            raise ValueError("action must be CONFIRM, REJECT, or NEED_MORE_INFO")
        if not reviewer:
            raise ValueError("reviewer is required")
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as connection:
            self._ensure_schema(connection)
            row = connection.execute("SELECT status FROM alert_case WHERE alert_id = ?", (alert_id,)).fetchone()
            if not row:
                raise ValueError("Alert not found")
            previous_status = row[0]
            new_status = {"CONFIRM": "CONFIRMED", "REJECT": "REJECTED"}.get(action, previous_status)
            review = ReviewRecord(self._next_review_id(connection), alert_id, reviewer, action, comment, timestamp)
            connection.execute(
                "INSERT INTO review_record (review_id, alert_id, reviewer, action, comment, created_time) VALUES (?, ?, ?, ?, ?, ?)",
                (review.review_id, review.alert_id, review.reviewer, review.action, review.comment, review.created_time),
            )
            if new_status != previous_status:
                connection.execute("UPDATE alert_case SET status = ?, updated_time = ? WHERE alert_id = ?", (new_status, timestamp, alert_id))
            detail = f"action={action}; previous_status={previous_status}; new_status={new_status}; comment={comment}"
            write_audit_log(connection, alert_id, "REVIEW_" + action, reviewer, timestamp, detail)
        return review

    def review_history(self, alert_id: str) -> dict[str, list[dict[str, str]]]:
        with self._connect() as connection:
            self._ensure_schema(connection)
            reviews = [ReviewRecord(*row).as_dict() for row in connection.execute(
                "SELECT review_id, alert_id, reviewer, action, comment, created_time FROM review_record WHERE alert_id = ? ORDER BY created_time", (alert_id,)
            )]
            audit = [AuditLog(*row).as_dict() for row in connection.execute(
                "SELECT log_id, alert_id, operation, operator, timestamp, detail FROM audit_log WHERE alert_id = ? ORDER BY timestamp", (alert_id,)
            )]
        return {"reviews": reviews, "audit_logs": audit}

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.warehouse_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(REVIEW_SCHEMA)

    @staticmethod
    def _next_review_id(connection: sqlite3.Connection) -> str:
        latest = connection.execute("SELECT review_id FROM review_record ORDER BY review_id DESC LIMIT 1").fetchone()
        return f"RV{(int(latest[0][2:]) + 1) if latest else 1:06d}"
