"""Generate a continuous stream of AML demo transactions.

This is a small Python runtime adapter for local demos. It deliberately writes
to ``data/realtime`` and never changes the curated IBM dataset. The generated
rows use the same transaction schema as the project and include normal traffic
plus deterministic cycle, structuring and fan-in patterns for rule-engine
demonstrations.
"""

from __future__ import annotations

import argparse
import csv
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


FIELDS = [
    "transaction_id",
    "timestamp",
    "from_bank",
    "from_account",
    "to_bank",
    "to_account",
    "amount_received",
    "receiving_currency",
    "amount_paid",
    "payment_currency",
    "payment_format",
]


def load_accounts(path: Path) -> list[tuple[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        accounts = [(str(row["bank_id"]), str(row["account_number"])) for row in rows]
    if len(accounts) < 6:
        raise ValueError("至少需要 6 个账户才能生成实时演示数据")
    return accounts


def next_id(path: Path) -> int:
    if not path.exists():
        return 1
    with path.open("r", encoding="utf-8", newline="") as handle:
        count = sum(1 for _ in handle) - 1
    return max(1, count + 1)


def row(tx_id: int, when: datetime, source: tuple[str, str], target: tuple[str, str], amount: float, fmt: str) -> dict[str, str]:
    amount_text = f"{amount:.2f}"
    stamp = when.astimezone(timezone.utc).strftime("%Y/%m/%d %H:%M:%S")
    return {
        "transaction_id": f"RT{tx_id:010d}",
        "timestamp": stamp,
        "from_bank": source[0],
        "from_account": source[1],
        "to_bank": target[0],
        "to_account": target[1],
        "amount_received": amount_text,
        "receiving_currency": "US Dollar",
        "amount_paid": amount_text,
        "payment_currency": "US Dollar",
        "payment_format": fmt,
    }


def generate_batch(accounts: list[tuple[str, str]], start_id: int, now: datetime, rng: random.Random, batch_size: int) -> list[dict[str, str]]:
    """Build one batch; every fifth batch contains an explicit suspicious motif."""
    batch: list[dict[str, str]] = []
    tx_id = start_id
    for index in range(batch_size):
        source, target = rng.sample(accounts, 2)
        batch.append(row(tx_id, now + timedelta(seconds=index), source, target, rng.uniform(80, 8000), "Wire"))
        tx_id += 1

    batch_no = start_id // max(batch_size, 1)
    if batch_no % 5 == 0:
        a, b, c = rng.sample(accounts, 3)
        batch.extend([
            row(tx_id, now, a, b, 4800, "Wire"),
            row(tx_id + 1, now + timedelta(seconds=2), b, c, 4700, "Wire"),
            row(tx_id + 2, now + timedelta(seconds=4), c, a, 4600, "Wire"),
        ])
        tx_id += 3
        fanin_target = rng.choice(accounts)
        for source in rng.sample([account for account in accounts if account != fanin_target], 4):
            batch.append(row(tx_id, now + timedelta(seconds=6), source, fanin_target, 3200, "ACH"))
            tx_id += 1
        splitter = rng.choice(accounts)
        for target in rng.sample([account for account in accounts if account != splitter], 5):
            batch.append(row(tx_id, now + timedelta(seconds=8), splitter, target, 950, "Wire"))
            tx_id += 1
    return batch


def run(args: argparse.Namespace) -> None:
    accounts = load_accounts(args.accounts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    new_file = not args.output.exists()
    tx_id = next_id(args.output)
    rng = random.Random(args.seed)
    simulation_time = datetime.now(timezone.utc)
    with args.output.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        batch_no = 0
        while args.max_batches <= 0 or batch_no < args.max_batches:
            batch = generate_batch(accounts, tx_id, simulation_time, rng, args.batch_size)
            writer.writerows(batch)
            handle.flush()
            tx_id += len(batch)
            batch_no += 1
            print(f"batch={batch_no} appended={len(batch)} total_next_id={tx_id}", flush=True)
            simulation_time += timedelta(minutes=args.interval_seconds / 60)
            if args.max_batches <= 0 or batch_no < args.max_batches:
                time.sleep(args.interval_seconds)


def parser() -> argparse.ArgumentParser:
    current = Path(__file__).resolve().parents[2]
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--accounts", type=Path, default=current / "data" / "accounts.csv")
    result.add_argument("--output", type=Path, default=current / "data" / "realtime" / "transactions.csv")
    result.add_argument("--interval-seconds", type=float, default=5.0)
    result.add_argument("--batch-size", type=int, default=20)
    result.add_argument("--max-batches", type=int, default=0, help="0 表示持续运行")
    result.add_argument("--seed", type=int, default=20260802)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
