#!/usr/bin/env python3
"""Build a graph-friendly AML dataset from raw IBM AML-Data HI-Small files.

The laundering label is used only to select complete laundering attempts and is
written to a separate labels.csv file.  It is deliberately excluded from the
transactions.csv file consumed by the demo application.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


TRANSACTION_COLUMNS = [
    "Timestamp",
    "From Bank",
    "From Account",
    "To Bank",
    "To Account",
    "Amount Received",
    "Receiving Currency",
    "Amount Paid",
    "Payment Currency",
    "Payment Format",
    "Is Laundering",
]

PUBLIC_TRANSACTION_COLUMNS = [
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

DEFAULT_PATTERNS = [
    "CYCLE",
    "FAN-OUT",
    "FAN-IN",
    "GATHER-SCATTER",
    "SCATTER-GATHER",
    "BIPARTITE",
]

DEFAULT_TARGET_EDGES = {
    "CYCLE": 8,
    "FAN-OUT": 10,
    "FAN-IN": 10,
    "GATHER-SCATTER": 14,
    "SCATTER-GATHER": 14,
    "BIPARTITE": 8,
    "STACK": 10,
    "RANDOM": 6,
}


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y/%m/%d %H:%M")


def normalize_bank(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        return str(int(value))
    return value


def account_key(bank: str, account: str) -> str:
    return f"{normalize_bank(bank)}::{account.strip()}"


def row_signature(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[column].strip() for column in TRANSACTION_COLUMNS)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class LaunderingCase:
    source_index: int
    pattern_type: str
    description: str
    rows: list[dict[str, str]]

    @property
    def start(self) -> datetime:
        return min(parse_time(row["Timestamp"]) for row in self.rows)

    @property
    def end(self) -> datetime:
        return max(parse_time(row["Timestamp"]) for row in self.rows)

    @property
    def accounts(self) -> set[str]:
        result: set[str] = set()
        for row in self.rows:
            result.add(account_key(row["From Bank"], row["From Account"]))
            result.add(account_key(row["To Bank"], row["To Account"]))
        return result


def parse_patterns(path: Path) -> list[LaunderingCase]:
    cases: list[LaunderingCase] = []
    current_type: str | None = None
    current_description = ""
    current_rows: list[dict[str, str]] = []
    source_index = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("BEGIN LAUNDERING ATTEMPT - "):
                remainder = line.removeprefix("BEGIN LAUNDERING ATTEMPT - ")
                current_type, _, description = remainder.partition(":")
                current_type = current_type.strip().upper()
                current_description = description.strip()
                current_rows = []
                source_index += 1
                continue
            if line.startswith("END LAUNDERING ATTEMPT - "):
                if current_type and current_rows:
                    cases.append(
                        LaunderingCase(
                            source_index=source_index,
                            pattern_type=current_type,
                            description=current_description,
                            rows=current_rows,
                        )
                    )
                current_type = None
                current_rows = []
                continue
            if current_type:
                values = next(csv.reader([line]))
                if len(values) != len(TRANSACTION_COLUMNS):
                    raise ValueError(
                        f"Unexpected pattern row with {len(values)} fields: {line[:120]}"
                    )
                current_rows.append(dict(zip(TRANSACTION_COLUMNS, values)))
    return cases


def choose_cases(
    cases: list[LaunderingCase],
    pattern_types: list[str],
    cases_per_pattern: int,
    seed: int,
) -> list[LaunderingCase]:
    rng = random.Random(seed)
    grouped: dict[str, list[LaunderingCase]] = defaultdict(list)
    for case in cases:
        grouped[case.pattern_type].append(case)

    chosen: list[LaunderingCase] = []
    for pattern_type in pattern_types:
        candidates = grouped.get(pattern_type, [])
        if len(candidates) < cases_per_pattern:
            raise ValueError(
                f"Pattern {pattern_type!r} has {len(candidates)} cases; "
                f"{cases_per_pattern} requested"
            )
        # Choose cases near a presentation-friendly target size. Tiny attempts
        # can be technically valid but fail to demonstrate multi-hop structure.
        target_edges = DEFAULT_TARGET_EDGES.get(
            pattern_type,
            round(statistics.median(len(case.rows) for case in candidates)),
        )
        rng.shuffle(candidates)
        candidates.sort(
            key=lambda case: (
                abs(len(case.rows) - target_edges),
                -len(case.accounts),
                case.source_index,
            )
        )
        selected = candidates[:cases_per_pattern]
        chosen.extend(selected)
    return sorted(chosen, key=lambda case: (case.start, case.pattern_type))


def source_row_to_internal(values: list[str]) -> dict[str, str]:
    if len(values) != len(TRANSACTION_COLUMNS):
        raise ValueError(f"Expected 11 transaction fields, got {len(values)}")
    return dict(zip(TRANSACTION_COLUMNS, values))


def collect_transactions(
    trans_path: Path,
    chosen_cases: list[LaunderingCase],
    context_days: int,
    max_context_transactions: int,
    background_transactions: int,
    seed: int,
) -> tuple[list[dict[str, str]], dict[tuple[str, ...], tuple[str, str]]]:
    selected_signatures: dict[tuple[str, ...], tuple[str, str]] = {}
    case_accounts: set[str] = set()
    case_windows: dict[str, tuple[datetime, datetime]] = {}

    for index, case in enumerate(chosen_cases, start=1):
        case_id = f"CASE{index:03d}"
        for row in case.rows:
            signature = row_signature(row)
            selected_signatures[signature] = (case_id, case.pattern_type)
        for key in case.accounts:
            case_accounts.add(key)
            start = case.start - timedelta(days=context_days)
            end = case.end + timedelta(days=context_days)
            if key in case_windows:
                old_start, old_end = case_windows[key]
                case_windows[key] = (min(start, old_start), max(end, old_end))
            else:
                case_windows[key] = (start, end)

    exact: dict[tuple[str, ...], dict[str, str]] = {}
    context_candidates: list[dict[str, str]] = []
    background_reservoir: list[dict[str, str]] = []
    rng = random.Random(seed)
    normal_seen = 0

    with trans_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if len(header) != len(TRANSACTION_COLUMNS):
            raise ValueError(f"Unexpected transaction header: {header}")

        for values in reader:
            row = source_row_to_internal(values)
            signature = row_signature(row)
            if signature in selected_signatures:
                exact[signature] = row
                continue

            if row["Is Laundering"].strip() != "0":
                continue

            timestamp = parse_time(row["Timestamp"])
            from_key = account_key(row["From Bank"], row["From Account"])
            to_key = account_key(row["To Bank"], row["To Account"])
            in_context = False
            for key in (from_key, to_key):
                window = case_windows.get(key)
                if window and window[0] <= timestamp <= window[1]:
                    in_context = True
                    break

            if in_context:
                context_candidates.append(row)
                continue

            normal_seen += 1
            if len(background_reservoir) < background_transactions:
                background_reservoir.append(row)
            else:
                slot = rng.randrange(normal_seen)
                if slot < background_transactions:
                    background_reservoir[slot] = row

    missing = set(selected_signatures) - set(exact)
    if missing:
        raise RuntimeError(
            f"{len(missing)} selected laundering transactions were not found "
            "in the source transaction file"
        )

    # Rows joining two case accounts are most useful for graph context.
    context_candidates.sort(
        key=lambda row: (
            -int(
                account_key(row["From Bank"], row["From Account"]) in case_accounts
                and account_key(row["To Bank"], row["To Account"]) in case_accounts
            ),
            row["Timestamp"],
            row["From Account"],
            row["To Account"],
        )
    )
    if len(context_candidates) > max_context_transactions:
        strong = [
            row
            for row in context_candidates
            if account_key(row["From Bank"], row["From Account"]) in case_accounts
            and account_key(row["To Bank"], row["To Account"]) in case_accounts
        ]
        remaining = [row for row in context_candidates if row not in strong]
        rng.shuffle(remaining)
        context_candidates = (
            strong[:max_context_transactions]
            + remaining[: max(0, max_context_transactions - len(strong))]
        )

    combined = list(exact.values()) + context_candidates + background_reservoir
    deduplicated: dict[tuple[str, ...], dict[str, str]] = {}
    for row in combined:
        deduplicated.setdefault(row_signature(row), row)
    rows = sorted(
        deduplicated.values(),
        key=lambda row: (
            parse_time(row["Timestamp"]),
            row["From Bank"],
            row["From Account"],
            row["To Bank"],
            row["To Account"],
            row["Amount Paid"],
        ),
    )
    return rows, selected_signatures


def load_accounts(path: Path, needed_keys: set[str]) -> dict[str, dict[str, str]]:
    accounts: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = account_key(row["Bank ID"], row["Account Number"])
            if key in needed_keys:
                accounts[key] = row
    return accounts


def write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    selected_signatures: dict[tuple[str, ...], tuple[str, str]],
    cases: list[LaunderingCase],
    accounts_source: Path,
    source_files: list[Path],
    args: argparse.Namespace,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transactions_path = output_dir / "transactions.csv"
    labels_path = output_dir / "labels.csv"
    accounts_path = output_dir / "accounts.csv"
    cases_path = output_dir / "cases.csv"

    needed_keys: set[str] = set()
    for row in rows:
        needed_keys.add(account_key(row["From Bank"], row["From Account"]))
        needed_keys.add(account_key(row["To Bank"], row["To Account"]))
    accounts = load_accounts(accounts_source, needed_keys)

    suspicious_count = 0
    pattern_counts: dict[str, int] = defaultdict(int)
    with (
        transactions_path.open("w", encoding="utf-8-sig", newline="") as tx_handle,
        labels_path.open("w", encoding="utf-8-sig", newline="") as label_handle,
    ):
        tx_writer = csv.DictWriter(tx_handle, fieldnames=PUBLIC_TRANSACTION_COLUMNS)
        label_fields = [
            "transaction_id",
            "is_laundering",
            "pattern_type",
            "case_id",
            "usage",
        ]
        label_writer = csv.DictWriter(label_handle, fieldnames=label_fields)
        tx_writer.writeheader()
        label_writer.writeheader()

        for index, row in enumerate(rows, start=1):
            transaction_id = f"TX{index:07d}"
            tx_writer.writerow(
                {
                    "transaction_id": transaction_id,
                    "timestamp": row["Timestamp"],
                    "from_bank": normalize_bank(row["From Bank"]),
                    "from_account": row["From Account"],
                    "to_bank": normalize_bank(row["To Bank"]),
                    "to_account": row["To Account"],
                    "amount_received": row["Amount Received"],
                    "receiving_currency": row["Receiving Currency"],
                    "amount_paid": row["Amount Paid"],
                    "payment_currency": row["Payment Currency"],
                    "payment_format": row["Payment Format"],
                }
            )
            case_id, pattern_type = selected_signatures.get(
                row_signature(row), ("", "")
            )
            is_laundering = int(bool(case_id))
            suspicious_count += is_laundering
            if pattern_type:
                pattern_counts[pattern_type] += 1
            label_writer.writerow(
                {
                    "transaction_id": transaction_id,
                    "is_laundering": is_laundering,
                    "pattern_type": pattern_type,
                    "case_id": case_id,
                    "usage": "offline_evaluation_only",
                }
            )

    with accounts_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "bank_id",
            "account_number",
            "bank_name",
            "entity_id",
            "entity_name",
            "metadata_status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for key in sorted(needed_keys):
            bank_id, account_number = key.split("::", 1)
            row = accounts.get(key)
            writer.writerow(
                {
                    "bank_id": bank_id,
                    "account_number": account_number,
                    "bank_name": row["Bank Name"] if row else "",
                    "entity_id": row["Entity ID"] if row else "",
                    "entity_name": row["Entity Name"] if row else "",
                    "metadata_status": "matched" if row else "not_in_accounts_source",
                }
            )

    with cases_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "case_id",
            "pattern_type",
            "source_case_index",
            "description",
            "start_time",
            "end_time",
            "laundering_transactions",
            "involved_accounts",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, case in enumerate(cases, start=1):
            writer.writerow(
                {
                    "case_id": f"CASE{index:03d}",
                    "pattern_type": case.pattern_type,
                    "source_case_index": case.source_index,
                    "description": case.description,
                    "start_time": case.start.strftime("%Y/%m/%d %H:%M"),
                    "end_time": case.end.strftime("%Y/%m/%d %H:%M"),
                    "laundering_transactions": len(case.rows),
                    "involved_accounts": len(case.accounts),
                }
            )

    manifest: dict[str, object] = {
        "dataset_name": "IBM AML-Data HI-Small Demo Subset",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "license": "CDLA-Sharing-1.0",
        "source": "https://www.kaggle.com/datasets/ealtman2019/ibm-transactions-for-anti-money-laundering-aml",
        "configuration": {
            "seed": args.seed,
            "patterns": args.patterns,
            "cases_per_pattern": args.cases_per_pattern,
            "context_days": args.context_days,
            "max_context_transactions": args.max_context_transactions,
            "background_transactions": args.background_transactions,
        },
        "statistics": {
            "transactions": len(rows),
            "laundering_transactions": suspicious_count,
            "normal_transactions": len(rows) - suspicious_count,
            "accounts": len(needed_keys),
            "accounts_with_metadata": len(accounts),
            "cases": len(cases),
            "pattern_transaction_counts": dict(sorted(pattern_counts.items())),
            "time_start": min(parse_time(row["Timestamp"]) for row in rows).isoformat(),
            "time_end": max(parse_time(row["Timestamp"]) for row in rows).isoformat(),
        },
        "label_boundary": (
            "labels.csv is for offline evaluation only. Do not load it into "
            "rule detection, risk scoring, graph analysis, or Agent tools."
        ),
        "source_files": [
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in source_files
        ],
        "output_files": {},
    }
    for path in [transactions_path, accounts_path, labels_path, cases_path]:
        manifest["output_files"][path.name] = {
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Directory containing HI-Small_Trans.csv, HI-Small_accounts.csv, and HI-Small_Patterns.txt",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Destination directory for normalized CSV files and manifest.json",
    )
    parser.add_argument(
        "--patterns",
        nargs="+",
        default=DEFAULT_PATTERNS,
        help="Pattern types to include (default: six graph-friendly types)",
    )
    parser.add_argument("--cases-per-pattern", type=int, default=1)
    parser.add_argument("--context-days", type=int, default=2)
    parser.add_argument("--max-context-transactions", type=int, default=3500)
    parser.add_argument("--background-transactions", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing existing normalized output files",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.patterns = [item.strip().upper() for item in args.patterns]

    trans_path = args.raw_dir / "HI-Small_Trans.csv"
    accounts_path = args.raw_dir / "HI-Small_accounts.csv"
    patterns_path = args.raw_dir / "HI-Small_Patterns.txt"
    missing = [
        str(path)
        for path in (trans_path, accounts_path, patterns_path)
        if not path.is_file()
    ]
    if missing:
        parser.error("Missing required source files: " + ", ".join(missing))

    output_files = [
        args.output_dir / name
        for name in ("transactions.csv", "accounts.csv", "labels.csv", "cases.csv", "manifest.json")
    ]
    existing = [str(path) for path in output_files if path.exists()]
    if existing and not args.overwrite:
        parser.error(
            "Output files already exist. Use --overwrite only after confirming "
            "the target directory: " + ", ".join(existing)
        )

    cases = parse_patterns(patterns_path)
    chosen = choose_cases(
        cases, args.patterns, args.cases_per_pattern, args.seed
    )
    rows, selected_signatures = collect_transactions(
        trans_path=trans_path,
        chosen_cases=chosen,
        context_days=args.context_days,
        max_context_transactions=args.max_context_transactions,
        background_transactions=args.background_transactions,
        seed=args.seed,
    )
    manifest = write_outputs(
        output_dir=args.output_dir,
        rows=rows,
        selected_signatures=selected_signatures,
        cases=chosen,
        accounts_source=accounts_path,
        source_files=[trans_path, accounts_path, patterns_path],
        args=args,
    )
    print(json.dumps(manifest["statistics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
