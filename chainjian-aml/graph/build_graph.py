"""Import cleaned IBM AML data into Neo4j as an account-transfer graph.

The importer reads only accounts and transactions. Evaluation labels are never
loaded into Neo4j, so graph analysis cannot leak ground-truth laundering data.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.neo4j_client import NEO4J_DATABASE, close_neo4j_driver, get_neo4j_driver


def batched(rows: Iterable[dict[str, str]], batch_size: int) -> Iterable[list[dict[str, str]]]:
    batch: list[dict[str, str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def account_id(bank_id: str, account_number: str) -> str:
    return f"{bank_id}::{account_number}"


def create_schema() -> None:
    driver = get_neo4j_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run(
            "CREATE CONSTRAINT account_id_unique IF NOT EXISTS "
            "FOR (account:Account) REQUIRE account.account_id IS UNIQUE"
        ).consume()
        session.run(
            "CREATE INDEX transfer_transaction_id IF NOT EXISTS "
            "FOR ()-[transfer:TRANSFER]-() ON (transfer.transaction_id)"
        ).consume()


def import_accounts(rows: list[dict[str, str]], batch_size: int) -> int:
    query = """
    UNWIND $rows AS row
    MERGE (account:Account {account_id: row.account_id})
    SET account.bank_id = row.bank_id,
        account.account_number = row.account_number,
        account.bank_name = row.bank_name,
        account.entity_id = row.entity_id,
        account.entity_name = row.entity_name,
        account.metadata_status = row.metadata_status
    """
    prepared = [
        {**row, "account_id": account_id(row["bank_id"], row["account_number"])}
        for row in rows
    ]
    driver = get_neo4j_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        for batch in batched(prepared, batch_size):
            session.run(query, rows=batch).consume()
    return len(prepared)


def import_transfers(rows: list[dict[str, str]], batch_size: int) -> int:
    query = """
    UNWIND $rows AS row
    MATCH (source:Account {account_id: row.from_account_id})
    MATCH (target:Account {account_id: row.to_account_id})
    MERGE (source)-[transfer:TRANSFER {transaction_id: row.transaction_id}]->(target)
    SET transfer.timestamp = datetime(row.timestamp),
        transfer.amount_received = toFloat(row.amount_received),
        transfer.receiving_currency = row.receiving_currency,
        transfer.amount_paid = toFloat(row.amount_paid),
        transfer.payment_currency = row.payment_currency,
        transfer.payment_format = row.payment_format
    """
    prepared = [
        {
            **row,
            "from_account_id": account_id(row["from_bank"], row["from_account"]),
            "to_account_id": account_id(row["to_bank"], row["to_account"]),
        }
        for row in rows
    ]
    driver = get_neo4j_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        for batch in batched(prepared, batch_size):
            session.run(query, rows=batch).consume()
    return len(prepared)


def graph_counts() -> dict[str, int]:
    driver = get_neo4j_driver()
    with driver.session(database=NEO4J_DATABASE) as session:
        return session.run(
            "CALL () { MATCH (account:Account) RETURN count(account) AS accounts } "
            "CALL () { MATCH ()-[transfer:TRANSFER]->() RETURN count(transfer) AS transfers } "
            "RETURN accounts, transfers"
        ).single().data()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "cleaned")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    accounts_path = args.data_dir / "accounts.csv"
    transactions_path = args.data_dir / "transactions.csv"
    if not accounts_path.is_file() or not transactions_path.is_file():
        parser.error("Expected accounts.csv and transactions.csv in " + str(args.data_dir))

    try:
        create_schema()
        account_rows = read_csv(accounts_path)
        transaction_rows = read_csv(transactions_path)
        print({
            "accounts_imported": import_accounts(account_rows, args.batch_size),
            "transfers_imported": import_transfers(transaction_rows, args.batch_size),
            "graph": graph_counts(),
        })
    finally:
        close_neo4j_driver()


if __name__ == "__main__":
    main()
