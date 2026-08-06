"""Generate, persist, and query standard AML alert cases."""

from __future__ import annotations

import json
from core.database import sqlite3
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from app.alert_model import AlertCase
from app.evidence_service import load_evidence, save_evidence
from app.risk_score import calculate_risk_score, risk_level
from rules.models import Alert


APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_case (
    alert_id TEXT PRIMARY KEY,
    case_fingerprint TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    risk_score REAL NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('HIGH', 'MEDIUM', 'LOW')),
    rule_hits_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING', 'CONFIRMED', 'REJECTED')),
    created_time TEXT NOT NULL,
    updated_time TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_evidence (
    evidence_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    evidence_type TEXT NOT NULL,
    evidence_content TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_case_status_score ON alert_case(status, risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_alert_case_account ON alert_case(account_id);
CREATE INDEX IF NOT EXISTS idx_alert_evidence_alert ON alert_evidence(alert_id);
"""


class AlertService:
    def __init__(self, warehouse_path: Path) -> None:
        self.warehouse_path = warehouse_path

    def generate(self, rule_alerts: list[Alert]) -> list[AlertCase]:
        """Group rule findings by account, calculate score, and persist cases."""
        grouped: dict[str, list[Alert]] = defaultdict(list)
        for alert in rule_alerts:
            grouped[alert.account_id].append(alert)
        with self._connect() as connection:
            self._ensure_schema(connection)
            cases = [self._upsert_case(connection, account_id, findings) for account_id, findings in grouped.items()]
        return cases

    def list_alerts(self) -> list[AlertCase]:
        with self._connect() as connection:
            self._ensure_schema(connection)
            rows = connection.execute(
                "SELECT alert_id, account_id, risk_score, risk_level, rule_hits_json, status, created_time FROM alert_case ORDER BY risk_score DESC, created_time DESC"
            ).fetchall()
            return [self._row_to_case(connection, row) for row in rows]

    def get_alert(self, alert_id: str) -> AlertCase | None:
        with self._connect() as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                "SELECT alert_id, account_id, risk_score, risk_level, rule_hits_json, status, created_time FROM alert_case WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
            return self._row_to_case(connection, row) if row else None

    def _upsert_case(self, connection: sqlite3.Connection, account_id: str, findings: list[Alert]) -> AlertCase:
        rule_codes = sorted({hit.rule_code for finding in findings for hit in finding.rule_hits})
        evidence_items = [item for finding in findings for item in finding.evidence]
        transaction_ids = sorted({transaction_id for item in evidence_items for transaction_id in item.transaction_ids})
        fingerprint = sha256(f"{account_id}|{'|'.join(rule_codes)}|{'|'.join(transaction_ids)}".encode()).hexdigest()
        existing = connection.execute(
            "SELECT alert_id, created_time, status FROM alert_case WHERE case_fingerprint = ?", (fingerprint,)
        ).fetchone()
        alert_id = existing[0] if existing else self._next_alert_id(connection)
        created_time = existing[1] if existing else min(finding.created_time for finding in findings)
        status = existing[2] if existing else "PENDING"
        score = calculate_risk_score(rule_codes)
        connection.execute(
            """INSERT INTO alert_case (alert_id, case_fingerprint, account_id, risk_score, risk_level, rule_hits_json, status, created_time, updated_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_fingerprint) DO UPDATE SET risk_score=excluded.risk_score, risk_level=excluded.risk_level,
            rule_hits_json=excluded.rule_hits_json, updated_time=excluded.updated_time""",
            (alert_id, fingerprint, account_id, score, risk_level(score), json.dumps(rule_codes), status, created_time, max(finding.created_time for finding in findings)),
        )
        evidence = save_evidence(connection, alert_id, evidence_items)
        return AlertCase(alert_id, account_id, score, risk_level(score), rule_codes, evidence, status, created_time)

    def _next_alert_id(self, connection: sqlite3.Connection) -> str:
        latest = connection.execute("SELECT alert_id FROM alert_case ORDER BY alert_id DESC LIMIT 1").fetchone()
        sequence = int(latest[0][2:]) + 1 if latest else 1
        return f"AL{sequence:06d}"

    @staticmethod
    def _row_to_case(connection: sqlite3.Connection, row: tuple[object, ...]) -> AlertCase:
        return AlertCase(
            alert_id=str(row[0]), account_id=str(row[1]), risk_score=float(row[2]), risk_level=str(row[3]),
            rule_hits=json.loads(str(row[4])), evidence=load_evidence(connection, str(row[0])),
            status=str(row[5]), created_time=str(row[6]),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.warehouse_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(APP_SCHEMA)
