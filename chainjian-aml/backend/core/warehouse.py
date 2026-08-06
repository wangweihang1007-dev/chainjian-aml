"""Build the ODS → DWD → DWS → ADS SQLite warehouse for ChainJian AML.

Evaluation labels are retained only in the isolated ODS evaluation area and
are deliberately excluded from every DWD, DWS, and ADS transformation.
"""

from __future__ import annotations

import argparse
import csv
from core.database import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data"
DEFAULT_CLEAN_DIR = DEFAULT_RAW_DIR / "cleaned"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "warehouse" / "aml.db"  # legacy path token; connect() uses DATABASE_URL


SCHEMA = """
PRAGMA foreign_keys = ON;

-- ODS: immutable source-shaped data, traceable to an import batch.
CREATE TABLE ods_import_batches (
    batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    raw_data_path TEXT NOT NULL,
    cleaned_data_path TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (quality_status IN ('passed', 'failed'))
);
CREATE TABLE ods_accounts_raw (
    batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id),
    bank_id TEXT, account_number TEXT, bank_name TEXT, entity_id TEXT, entity_name TEXT, metadata_status TEXT
);
CREATE TABLE ods_transactions_raw (
    batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id),
    transaction_id TEXT, timestamp TEXT, from_bank TEXT, from_account TEXT, to_bank TEXT, to_account TEXT,
    amount_received TEXT, receiving_currency TEXT, amount_paid TEXT, payment_currency TEXT, payment_format TEXT
);
CREATE TABLE ods_cases_raw (
    batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id),
    case_id TEXT, pattern_type TEXT, source_case_index TEXT, description TEXT, start_time TEXT, end_time TEXT,
    laundering_transactions TEXT, involved_accounts TEXT
);
-- Evaluation-only isolation zone. No DWD/DWS/ADS SQL may reference this table.
CREATE TABLE ods_evaluation_labels_raw (
    batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id),
    transaction_id TEXT, is_laundering TEXT, pattern_type TEXT, case_id TEXT, usage TEXT
);

-- DWD: conformed, cleaned detail data used by rules, graph export and Agent tools.
CREATE TABLE dim_account (
    account_id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    account_number TEXT NOT NULL,
    bank_name TEXT,
    entity_id TEXT,
    entity_name TEXT,
    metadata_status TEXT NOT NULL,
    effective_batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id),
    UNIQUE (bank_id, account_number)
);
CREATE TABLE dwd_transaction_detail (
    transaction_id TEXT PRIMARY KEY,
    transaction_time TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    from_account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    to_account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    amount_received NUMERIC NOT NULL CHECK (amount_received > 0),
    receiving_currency TEXT NOT NULL,
    amount_paid NUMERIC NOT NULL CHECK (amount_paid > 0),
    payment_currency TEXT NOT NULL,
    payment_format TEXT NOT NULL,
    is_self_transfer INTEGER NOT NULL CHECK (is_self_transfer IN (0, 1)),
    effective_batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id)
);
CREATE TABLE dwd_case_detail (
    case_id TEXT PRIMARY KEY,
    pattern_type TEXT NOT NULL,
    source_case_index INTEGER,
    description TEXT,
    start_time TEXT,
    end_time TEXT,
    laundering_transactions INTEGER,
    involved_accounts INTEGER,
    effective_batch_id INTEGER NOT NULL REFERENCES ods_import_batches(batch_id)
);

-- DWS: reusable account-day and account-level feature aggregates.
CREATE TABLE dws_account_daily (
    transaction_date TEXT NOT NULL,
    account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    outbound_transaction_count INTEGER NOT NULL,
    inbound_transaction_count INTEGER NOT NULL,
    outbound_amount NUMERIC NOT NULL,
    inbound_amount NUMERIC NOT NULL,
    counterparty_count INTEGER NOT NULL,
    self_transfer_count INTEGER NOT NULL,
    PRIMARY KEY (transaction_date, account_id)
);
CREATE TABLE dws_account_risk_features (
    account_id TEXT PRIMARY KEY REFERENCES dim_account(account_id),
    active_days INTEGER NOT NULL,
    total_transaction_count INTEGER NOT NULL,
    outbound_transaction_count INTEGER NOT NULL,
    inbound_transaction_count INTEGER NOT NULL,
    outbound_amount NUMERIC NOT NULL,
    inbound_amount NUMERIC NOT NULL,
    counterparty_count INTEGER NOT NULL,
    self_transfer_count INTEGER NOT NULL,
    refreshed_at TEXT NOT NULL
);

-- APP: mutable investigation workflow records.
CREATE TABLE app_alerts (
    alert_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    risk_score REAL NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected', 'needs_review')),
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE app_rule_hits (
    rule_hit_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES app_alerts(alert_id),
    rule_code TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    explanation TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE app_alert_evidence (
    alert_id TEXT NOT NULL REFERENCES app_alerts(alert_id),
    transaction_id TEXT NOT NULL REFERENCES dwd_transaction_detail(transaction_id),
    evidence_type TEXT NOT NULL,
    detail TEXT,
    PRIMARY KEY (alert_id, transaction_id, evidence_type)
);
CREATE TABLE app_review_actions (
    action_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES app_alerts(alert_id),
    operator_id TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('confirm', 'reject', 'request_more_info', 'note', 'status_change')),
    previous_status TEXT, new_status TEXT, comment TEXT, evidence_version TEXT, created_at TEXT NOT NULL
);
CREATE TABLE app_reports (
    report_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES app_alerts(alert_id),
    content_markdown TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    reviewer_note TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
-- Canonical Alert Layer cases consumed by frontend, reviewers, and Agent tools.
CREATE TABLE alert_case (
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
CREATE TABLE alert_evidence (
    evidence_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    evidence_type TEXT NOT NULL,
    evidence_content TEXT NOT NULL
);
CREATE TABLE review_record (
    review_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    reviewer TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('CONFIRM', 'REJECT', 'NEED_MORE_INFO')),
    comment TEXT NOT NULL,
    created_time TEXT NOT NULL
);
CREATE TABLE audit_log (
    log_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert_case(alert_id),
    operation TEXT NOT NULL,
    operator TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    detail TEXT NOT NULL
);

-- ADS: screen-ready marts. Labels remain unavailable in this layer.
CREATE TABLE ads_dashboard_summary (
    snapshot_at TEXT PRIMARY KEY,
    total_accounts INTEGER NOT NULL,
    total_transactions INTEGER NOT NULL,
    total_transaction_amount NUMERIC NOT NULL,
    active_accounts INTEGER NOT NULL,
    alert_count INTEGER NOT NULL,
    high_risk_alert_count INTEGER NOT NULL,
    pending_alert_count INTEGER NOT NULL
);
CREATE TABLE ads_account_activity_rank (
    snapshot_at TEXT NOT NULL,
    activity_rank INTEGER NOT NULL,
    account_id TEXT NOT NULL REFERENCES dim_account(account_id),
    total_transaction_count INTEGER NOT NULL,
    total_transaction_amount NUMERIC NOT NULL,
    counterparty_count INTEGER NOT NULL,
    PRIMARY KEY (snapshot_at, account_id)
);
CREATE VIEW ads_alert_dashboard AS
SELECT a.alert_id, a.account_id, a.risk_score, a.risk_level, a.status, a.summary, a.created_at, a.updated_at,
       d.bank_id, d.account_number, d.entity_name
FROM app_alerts a JOIN dim_account d ON d.account_id = a.account_id;

CREATE INDEX idx_dwd_transaction_date ON dwd_transaction_detail(transaction_date);
CREATE INDEX idx_dwd_transaction_from ON dwd_transaction_detail(from_account_id);
CREATE INDEX idx_dwd_transaction_to ON dwd_transaction_detail(to_account_id);
CREATE INDEX idx_app_alert_status_risk ON app_alerts(status, risk_score DESC);
CREATE INDEX idx_alert_case_status_score ON alert_case(status, risk_score DESC);
CREATE INDEX idx_alert_case_account ON alert_case(account_id);
CREATE INDEX idx_alert_evidence_alert ON alert_evidence(alert_id);
CREATE INDEX idx_review_alert_time ON review_record(alert_id, created_time);
CREATE INDEX idx_audit_alert_time ON audit_log(alert_id, timestamp);
"""


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def account_id(bank_id: str, account_number: str) -> str:
    return f"{bank_id}::{account_number}"


def connect(path: Path | str = DEFAULT_DATABASE) -> sqlite3.Connection:
    return sqlite3.connect(path)


def require_files(directory: Path, names: tuple[str, ...]) -> None:
    missing = [str(directory / name) for name in names if not (directory / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing input files: " + ", ".join(missing))


def build_warehouse(raw_dir: Path, clean_dir: Path, database_path: Path, replace: bool = False) -> dict[str, int]:
    require_files(raw_dir, ("accounts.csv", "transactions.csv", "labels.csv", "cases.csv"))
    require_files(clean_dir, ("accounts.csv", "transactions.csv", "cases.csv"))
    if replace:
        with connect(database_path) as connection:
            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public")

    raw_accounts, raw_transactions = read_rows(raw_dir / "accounts.csv"), read_rows(raw_dir / "transactions.csv")
    raw_labels, raw_cases = read_rows(raw_dir / "labels.csv"), read_rows(raw_dir / "cases.csv")
    accounts, transactions, cases = read_rows(clean_dir / "accounts.csv"), read_rows(clean_dir / "transactions.csv"), read_rows(clean_dir / "cases.csv")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        batch_id = connection.execute(
            "INSERT INTO ods_import_batches (source_name, raw_data_path, cleaned_data_path, imported_at, quality_status) VALUES (?, ?, ?, ?, 'passed')",
            ("IBM AML cleaned dataset", str(raw_dir), str(clean_dir), now),
        ).lastrowid
        connection.executemany("INSERT INTO ods_accounts_raw VALUES (?, ?, ?, ?, ?, ?, ?)", [(batch_id, r["bank_id"], r["account_number"], r["bank_name"], r["entity_id"], r["entity_name"], r["metadata_status"]) for r in raw_accounts])
        connection.executemany("INSERT INTO ods_transactions_raw VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(batch_id, r["transaction_id"], r["timestamp"], r["from_bank"], r["from_account"], r["to_bank"], r["to_account"], r["amount_received"], r["receiving_currency"], r["amount_paid"], r["payment_currency"], r["payment_format"]) for r in raw_transactions])
        connection.executemany("INSERT INTO ods_cases_raw VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(batch_id, r["case_id"], r["pattern_type"], r["source_case_index"], r["description"], r["start_time"], r["end_time"], r["laundering_transactions"], r["involved_accounts"]) for r in raw_cases])
        connection.executemany("INSERT INTO ods_evaluation_labels_raw VALUES (?, ?, ?, ?, ?, ?)", [(batch_id, r["transaction_id"], r["is_laundering"], r["pattern_type"], r["case_id"], r["usage"]) for r in raw_labels])
        connection.executemany("INSERT INTO dim_account VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [(account_id(r["bank_id"], r["account_number"]), r["bank_id"], r["account_number"], r["bank_name"], r["entity_id"], r["entity_name"], r["metadata_status"], batch_id) for r in accounts])
        connection.executemany("INSERT INTO dwd_transaction_detail VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(r["transaction_id"], r["timestamp"], r["timestamp"][:10], account_id(r["from_bank"], r["from_account"]), account_id(r["to_bank"], r["to_account"]), r["amount_received"], r["receiving_currency"], r["amount_paid"], r["payment_currency"], r["payment_format"], int(account_id(r["from_bank"], r["from_account"]) == account_id(r["to_bank"], r["to_account"])), batch_id) for r in transactions])
        connection.executemany("INSERT INTO dwd_case_detail VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(r["case_id"], r["pattern_type"], r["source_case_index"], r["description"], r["start_time"], r["end_time"], r["laundering_transactions"], r["involved_accounts"], batch_id) for r in cases])
        build_dws(connection, now)
        build_ads(connection, now)
        tables = ("ods_accounts_raw", "ods_transactions_raw", "ods_evaluation_labels_raw", "dim_account", "dwd_transaction_detail", "dws_account_daily", "dws_account_risk_features", "ads_dashboard_summary", "ads_account_activity_rank")
        return {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in tables}


def build_dws(connection: sqlite3.Connection, now: str) -> None:
    connection.execute("DELETE FROM dws_account_daily")
    connection.execute("DELETE FROM dws_account_risk_features")
    connection.execute("""
        INSERT INTO dws_account_daily
        WITH flows AS (
            SELECT transaction_date, from_account_id AS account_id, to_account_id AS counterparty_id,
                   1 AS outbound_count, 0 AS inbound_count, amount_paid AS outbound_amount, 0 AS inbound_amount, is_self_transfer
            FROM dwd_transaction_detail
            UNION ALL
            SELECT transaction_date, to_account_id, from_account_id,
                   0, 1, 0, amount_received, is_self_transfer
            FROM dwd_transaction_detail
        )
        SELECT transaction_date, account_id, SUM(outbound_count), SUM(inbound_count), SUM(outbound_amount), SUM(inbound_amount),
               COUNT(DISTINCT counterparty_id), SUM(is_self_transfer)
        FROM flows GROUP BY transaction_date, account_id
    """)
    connection.execute("""
        INSERT INTO dws_account_risk_features
        SELECT account_id, COUNT(*), SUM(outbound_transaction_count + inbound_transaction_count), SUM(outbound_transaction_count),
               SUM(inbound_transaction_count), SUM(outbound_amount), SUM(inbound_amount), MAX(counterparty_count),
               SUM(self_transfer_count), ?
        FROM dws_account_daily GROUP BY account_id
    """, (now,))


def build_ads(connection: sqlite3.Connection, now: str) -> None:
    connection.execute("DELETE FROM ads_dashboard_summary")
    connection.execute("DELETE FROM ads_account_activity_rank")
    connection.execute("""
        INSERT INTO ads_dashboard_summary
        SELECT ?, (SELECT count(*) FROM dim_account), (SELECT count(*) FROM dwd_transaction_detail),
               COALESCE((SELECT sum(amount_paid) FROM dwd_transaction_detail), 0),
               (SELECT count(*) FROM dws_account_risk_features),
               (SELECT count(*) FROM app_alerts),
               (SELECT count(*) FROM app_alerts WHERE risk_level = 'high'),
               (SELECT count(*) FROM app_alerts WHERE status = 'pending')
    """, (now,))
    connection.execute("""
        INSERT INTO ads_account_activity_rank
        SELECT ?, ROW_NUMBER() OVER (ORDER BY total_transaction_count DESC, (outbound_amount + inbound_amount) DESC),
               account_id, total_transaction_count, outbound_amount + inbound_amount, counterparty_count
        FROM dws_account_risk_features
    """, (now,))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the ChainJian AML layered PostgreSQL warehouse.")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--replace", action="store_true", help="Replace an existing local warehouse database.")
    args = parser.parse_args()
    print(build_warehouse(args.raw_dir, args.clean_dir, args.database, args.replace))


if __name__ == "__main__":
    main()
