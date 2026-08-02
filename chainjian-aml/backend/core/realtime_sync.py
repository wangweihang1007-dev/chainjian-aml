"""Idempotent incremental sync from the realtime CSV into SQLite and Neo4j."""

from __future__ import annotations

import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from backend.core.neo4j_client import run_write
from core.neo4j_client import get_neo4j_driver
from core.warehouse import DEFAULT_DATABASE, account_id, build_ads, build_dws, connect, SCHEMA
from rules.rule_engine import RuleEngine
from app.alert_service import AlertService

LOGGER = logging.getLogger("chainjian.realtime_sync")


def _load_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _state_path(input_path: Path) -> Path:
    return input_path.with_name("sync_state.json")


def _read_state(input_path: Path) -> set[str]:
    path = _state_path(input_path)
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")).get("transaction_ids", []))
    except (OSError, ValueError):
        LOGGER.warning("Invalid sync state; falling back to DWD idempotency")
        return set()


def _write_state(input_path: Path, transaction_ids: set[str]) -> None:
    _state_path(input_path).write_text(json.dumps({"transaction_ids": sorted(transaction_ids)}, ensure_ascii=False), encoding="utf-8")


def _sync_sqlite(rows: list[dict[str, str]], database_path: Path) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(database_path) as connection:
        batch_id = connection.execute(
            "INSERT INTO ods_import_batches (source_name, raw_data_path, cleaned_data_path, imported_at, quality_status) VALUES (?, ?, ?, ?, 'passed')",
            ("realtime simulator", "data/realtime/transactions.csv", "data/realtime/transactions.csv", now),
        ).lastrowid
        inserted = 0
        for row in rows:
            source_id = account_id(row["from_bank"], row["from_account"])
            target_id = account_id(row["to_bank"], row["to_account"])
            if len(connection.execute("SELECT 1 FROM dim_account WHERE account_id IN (?, ?)", (source_id, target_id)).fetchall()) != 2:
                raise ValueError(f"Realtime transaction references unknown account(s): {source_id}, {target_id}")
            connection.execute("INSERT OR IGNORE INTO ods_transactions_raw VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (batch_id, row["transaction_id"], row["timestamp"], row["from_bank"], row["from_account"], row["to_bank"], row["to_account"], row["amount_received"], row["receiving_currency"], row["amount_paid"], row["payment_currency"], row["payment_format"]))
            cursor = connection.execute("""INSERT OR IGNORE INTO dwd_transaction_detail VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (row["transaction_id"], row["timestamp"], row["timestamp"][:10], source_id, target_id, float(row["amount_received"]), row["receiving_currency"], float(row["amount_paid"]), row["payment_currency"], row["payment_format"], int(source_id == target_id), batch_id))
            inserted += cursor.rowcount
        if inserted:
            build_dws(connection, now)
            build_ads(connection, now)
        return inserted


def _sync_neo4j(rows: list[dict[str, str]]) -> None:
    query = """
    UNWIND $rows AS item
    MERGE (source:Account {account_id: item.source_id})
    MERGE (target:Account {account_id: item.target_id})
    MERGE (source)-[transfer:TRANSFER {transaction_id: item.transaction_id}]->(target)
    SET transfer.timestamp = item.timestamp, transfer.amount_paid = item.amount_paid,
        transfer.payment_currency = item.payment_currency, transfer.payment_format = item.payment_format
    """
    payload = [{
        "source_id": account_id(item["from_bank"], item["from_account"]), "target_id": account_id(item["to_bank"], item["to_account"]),
        "transaction_id": item["transaction_id"], "timestamp": item["timestamp"], "amount_paid": float(item["amount_paid"]),
        "payment_currency": item["payment_currency"], "payment_format": item["payment_format"],
    } for item in rows]
    run_write(query, {"rows": payload})


def sync_once(input_path: Path, database_path: Path = DEFAULT_DATABASE, trigger_rules: bool = True) -> dict[str, Any]:
    all_rows = _load_rows(input_path)
    seen = _read_state(input_path)
    new_rows = [row for row in all_rows if row.get("transaction_id") and row["transaction_id"] not in seen]
    if not new_rows:
        return {"new_rows": 0, "sqlite_inserted": 0, "neo4j_synced": 0, "alerts": 0}
    inserted = _sync_sqlite(new_rows, database_path)
    neo4j_synced = 0
    neo4j_error = None
    try:
        _sync_neo4j(new_rows)
        neo4j_synced = len(new_rows)
    except Exception as error:  # keep SQLite data and retry Neo4j on the next cycle
        neo4j_error = str(error)
        LOGGER.exception("Neo4j sync failed")
    # Only advance the source checkpoint after Neo4j accepts the batch. This
    # keeps failed graph writes retryable while SQLite remains idempotent.
    if neo4j_synced:
        _write_state(input_path, seen | {row["transaction_id"] for row in new_rows})
    alerts = 0
    if trigger_rules and neo4j_synced:
        findings = RuleEngine(database_path).run()
        alerts = len(AlertService(database_path).generate(findings))
    result = {"new_rows": len(new_rows), "sqlite_inserted": inserted, "neo4j_synced": neo4j_synced, "neo4j_error": neo4j_error, "alerts": alerts}
    with connect(database_path) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS realtime_sync_run (created_at TEXT NOT NULL, status TEXT NOT NULL, new_rows INTEGER NOT NULL, sqlite_inserted INTEGER NOT NULL, neo4j_synced INTEGER NOT NULL, error TEXT)""")
        connection.execute("INSERT INTO realtime_sync_run VALUES (?, ?, ?, ?, ?, ?)", (datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed" if not neo4j_error else "partial", len(new_rows), inserted, neo4j_synced, neo4j_error))
    return result
