"""Serialize and retrieve traceable APP-layer alert evidence."""

from __future__ import annotations

import json
from core.database import sqlite3
from hashlib import sha256

from app.alert_model import AlertEvidence
from rules.models import Evidence


def evidence_id(alert_id: str, evidence: Evidence) -> str:
    payload = json.dumps(
        {"type": evidence.evidence_type, "transactions": evidence.transaction_ids, "path": evidence.account_path},
        sort_keys=True,
    )
    return f"EV-{sha256(f'{alert_id}|{payload}'.encode()).hexdigest()[:16]}"


def save_evidence(connection: sqlite3.Connection, alert_id: str, evidence_items: list[Evidence]) -> list[AlertEvidence]:
    saved: list[AlertEvidence] = []
    for item in evidence_items:
        identifier = evidence_id(alert_id, item)
        content = {
            "path": "->".join(item.account_path),
            "account_path": item.account_path,
            "transactions": item.transaction_ids,
            **item.details,
        }
        connection.execute(
            """INSERT INTO alert_evidence (evidence_id, alert_id, evidence_type, evidence_content)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(evidence_id) DO UPDATE SET evidence_content=excluded.evidence_content""",
            (identifier, alert_id, item.evidence_type, json.dumps(content, ensure_ascii=False, default=str)),
        )
        saved.append(AlertEvidence(identifier, alert_id, item.evidence_type, content))
    return saved


def load_evidence(connection: sqlite3.Connection, alert_id: str) -> list[AlertEvidence]:
    rows = connection.execute(
        "SELECT evidence_id, alert_id, evidence_type, evidence_content FROM alert_evidence WHERE alert_id = ? ORDER BY evidence_id",
        (alert_id,),
    ).fetchall()
    return [AlertEvidence(row[0], row[1], row[2], json.loads(row[3])) for row in rows]
