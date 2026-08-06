"""Generate a reproducible, case-grouped AML benchmark for offline calibration.

The benchmark is deliberately separate from the operational warehouse. Labels
are emitted only to the evaluation artifact and never imported into inference.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


PATTERNS = ("CYCLE", "FAN-IN", "FAN-OUT", "SCATTER-GATHER", "GATHER-SCATTER", "BIPARTITE")
TX_FIELDS = ("transaction_id", "timestamp", "from_account", "to_account", "amount", "case_id", "pattern_type", "is_laundering")


@dataclass(frozen=True)
class Tx:
    transaction_id: str
    timestamp: str
    from_account: str
    to_account: str
    amount: float
    case_id: str
    pattern_type: str
    is_laundering: int


def _tx(index: int, when: datetime, source: str, target: str, amount: float, case_id: str = "NORMAL") -> Tx:
    pattern = "NORMAL" if case_id == "NORMAL" else case_id.split("-")[1]
    return Tx(f"SYN{index:09d}", when.isoformat(timespec="seconds"), source, target, round(amount, 2), case_id, pattern, int(case_id != "NORMAL"))


def generate(cases_per_pattern: int = 100, normal_transactions: int = 5000, seed: int = 20260806) -> list[Tx]:
    rng = random.Random(seed)
    now = datetime(2022, 1, 1)
    result: list[Tx] = []
    index = 1
    accounts = [f"N-{i:06d}" for i in range(cases_per_pattern * 20)]
    for _ in range(normal_transactions):
        source, target = rng.sample(accounts, 2)
        result.append(_tx(index, now + timedelta(seconds=index), source, target, rng.uniform(50, 9000)))
        index += 1
    case_no = 1
    for pattern in PATTERNS:
        for _ in range(cases_per_pattern):
            case_id = f"CASE-{case_no:05d}-{pattern}"
            base = f"C{case_no:05d}"
            when = now + timedelta(days=case_no % 30, minutes=case_no)
            edges: list[tuple[str, str, float]] = []
            if pattern == "CYCLE":
                nodes = [f"{base}-A{i}" for i in range(4)]
                edges = [(nodes[i], nodes[(i + 1) % 4], rng.uniform(4000, 7000)) for i in range(4)]
            elif pattern == "FAN-IN":
                target = f"{base}-T"; edges = [(f"{base}-S{i}", target, rng.uniform(1500, 9000)) for i in range(6)]
            elif pattern == "FAN-OUT":
                source = f"{base}-S"; edges = [(source, f"{base}-T{i}", rng.uniform(1500, 9000)) for i in range(6)]
            elif pattern == "SCATTER-GATHER":
                source, target = f"{base}-S", f"{base}-T"
                edges = [(source, f"{base}-M{i}", rng.uniform(4000, 9000)) for i in range(6)]
                edges += [(f"{base}-M{i}", target, rng.uniform(3500, 8500)) for i in range(6)]
            elif pattern == "GATHER-SCATTER":
                middle = f"{base}-M"
                edges = [(f"{base}-S{i}", middle, rng.uniform(4000, 9000)) for i in range(6)]
                edges += [(middle, f"{base}-T{i}", rng.uniform(3500, 8500)) for i in range(6)]
            else:
                sources = [f"{base}-S{i}" for i in range(3)]; targets = [f"{base}-T{i}" for i in range(3)]
                edges = [(source, target, rng.uniform(3000, 9000)) for source in sources for target in targets]
            for offset, (source, target, amount) in enumerate(edges):
                result.append(_tx(index, when + timedelta(seconds=offset * 7), source, target, amount, case_id)); index += 1
            case_no += 1
    return result


def split_by_case(rows: list[Tx], seed: int = 20260806) -> dict[str, list[Tx]]:
    rng = random.Random(seed)
    case_ids = sorted({row.case_id for row in rows})
    rng.shuffle(case_ids)
    n = len(case_ids); cut1, cut2 = int(n * 0.6), int(n * 0.8)
    groups = {"train": set(case_ids[:cut1]), "validation": set(case_ids[cut1:cut2]), "test": set(case_ids[cut2:])}
    return {name: [row for row in rows if row.case_id in ids] for name, ids in groups.items()}


def write_benchmark(output_dir: Path, cases_per_pattern: int, normal_transactions: int, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    splits = split_by_case(generate(cases_per_pattern, normal_transactions, seed), seed)
    for name, rows in splits.items():
        with (output_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TX_FIELDS); writer.writeheader()
            writer.writerows(row.__dict__ for row in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("data/evaluation_benchmark"))
    parser.add_argument("--cases-per-pattern", type=int, default=100)
    parser.add_argument("--normal-transactions", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260806)
    args = parser.parse_args(); write_benchmark(args.output_dir, args.cases_per_pattern, args.normal_transactions, args.seed)
