"""Clean and validate AML CSV data without exposing evaluation labels to inference.

The output is a separate, reproducible dataset. Source files in ``data/`` are
never changed by this module.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


ACCOUNT_FIELDS = [
    "bank_id", "account_number", "bank_name", "entity_id", "entity_name", "metadata_status"
]
TRANSACTION_FIELDS = [
    "transaction_id", "timestamp", "from_bank", "from_account", "to_bank", "to_account",
    "amount_received", "receiving_currency", "amount_paid", "payment_currency", "payment_format",
]
LABEL_FIELDS = ["transaction_id", "is_laundering", "pattern_type", "case_id", "usage"]
CASE_FIELDS = [
    "case_id", "pattern_type", "source_case_index", "description", "start_time", "end_time",
    "laundering_transactions", "involved_accounts",
]


def account_key(bank_id: str, account_number: str) -> str:
    return f"{bank_id.strip()}::{account_number.strip()}"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fields: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def normalize_timestamp(value: str) -> str:
    return datetime.strptime(value, "%Y/%m/%d %H:%M").isoformat(timespec="seconds")


def normalize_amount(value: str) -> str:
    amount = Decimal(value)
    if not amount.is_finite() or amount <= 0:
        raise InvalidOperation
    # Preserve source precision: rounding a valid micro-transaction to 0.00
    # would silently violate the transaction fact table's positive-value rule.
    return format(amount.normalize(), "f")


def clean_accounts(rows: list[dict[str, str]], report: dict[str, int]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in rows:
        row = {field: normalize_text(source.get(field)) for field in ACCOUNT_FIELDS}
        if not row["bank_id"] or not row["account_number"]:
            report["accounts_dropped_missing_key"] += 1
            continue
        key = account_key(row["bank_id"], row["account_number"])
        if key in seen:
            report["accounts_dropped_duplicate_key"] += 1
            continue
        seen.add(key)
        cleaned.append(row)
    return cleaned


def clean_transactions(
    rows: list[dict[str, str]], report: dict[str, int]
) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_payloads: set[tuple[str, ...]] = set()
    required = [
        "transaction_id", "timestamp", "from_bank", "from_account", "to_bank", "to_account",
        "amount_received", "receiving_currency", "amount_paid", "payment_currency", "payment_format",
    ]
    for source in rows:
        row = {field: normalize_text(source.get(field)) for field in TRANSACTION_FIELDS}
        if any(not row[field] for field in required):
            report["transactions_dropped_missing_required"] += 1
            continue
        try:
            row["timestamp"] = normalize_timestamp(row["timestamp"])
            row["amount_received"] = normalize_amount(row["amount_received"])
            row["amount_paid"] = normalize_amount(row["amount_paid"])
        except (ValueError, InvalidOperation):
            report["transactions_dropped_invalid_time_or_amount"] += 1
            continue
        if row["transaction_id"] in seen_ids:
            report["transactions_dropped_duplicate_id"] += 1
            continue
        payload = tuple(row[field] for field in TRANSACTION_FIELDS[1:])
        if payload in seen_payloads:
            report["transactions_dropped_duplicate_payload"] += 1
            continue
        seen_ids.add(row["transaction_id"])
        seen_payloads.add(payload)
        if account_key(row["from_bank"], row["from_account"]) == account_key(row["to_bank"], row["to_account"]):
            report["transactions_self_transfer_preserved"] += 1
        cleaned.append(row)
    return cleaned


def add_missing_accounts(
    accounts: list[dict[str, str]], transactions: list[dict[str, str]], report: dict[str, int]
) -> None:
    existing = {account_key(row["bank_id"], row["account_number"]) for row in accounts}
    for transaction in transactions:
        for bank_field, account_field in (("from_bank", "from_account"), ("to_bank", "to_account")):
            bank_id, account_number = transaction[bank_field], transaction[account_field]
            key = account_key(bank_id, account_number)
            if key not in existing:
                accounts.append({
                    "bank_id": bank_id, "account_number": account_number, "bank_name": "",
                    "entity_id": "", "entity_name": "", "metadata_status": "referenced_only",
                })
                existing.add(key)
                report["accounts_added_from_transaction_reference"] += 1


def clean_labels(rows: list[dict[str, str]], transaction_ids: set[str], report: dict[str, int]) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in rows:
        row = {field: normalize_text(source.get(field)) for field in LABEL_FIELDS}
        if not row["transaction_id"] or row["transaction_id"] not in transaction_ids:
            report["labels_dropped_unmatched_transaction"] += 1
            continue
        if row["transaction_id"] in seen:
            report["labels_dropped_duplicate_id"] += 1
            continue
        if row["is_laundering"] not in {"0", "1"}:
            report["labels_dropped_invalid_value"] += 1
            continue
        row["usage"] = "offline_evaluation_only"
        seen.add(row["transaction_id"])
        cleaned.append(row)
    return cleaned


def report_markdown(report: dict[str, int]) -> str:
    return f"""# 数据清洗报告

## 输出位置

- 清洗后数据：`data/cleaned/`
- 本报告由 `backend/core/data_cleaning.py` 自动生成。

## 清洗结果

| 检查或处理项 | 数量 |
| --- | ---: |
| 原始账户记录 | {report['accounts_input']} |
| 清洗后账户记录 | {report['accounts_output']} |
| 空账户主键删除 | {report['accounts_dropped_missing_key']} |
| 重复账户主键删除 | {report['accounts_dropped_duplicate_key']} |
| 交易引用但账户表缺失、已补全 | {report['accounts_added_from_transaction_reference']} |
| 原始交易记录 | {report['transactions_input']} |
| 清洗后交易记录 | {report['transactions_output']} |
| 空必填字段交易删除 | {report['transactions_dropped_missing_required']} |
| 非法时间或非正金额交易删除 | {report['transactions_dropped_invalid_time_or_amount']} |
| 重复交易 ID 删除 | {report['transactions_dropped_duplicate_id']} |
| 重复交易内容删除 | {report['transactions_dropped_duplicate_payload']} |
| 自转交易（保留） | {report['transactions_self_transfer_preserved']} |
| 清洗后评估标签 | {report['labels_output']} |
| 无匹配交易标签删除 | {report['labels_dropped_unmatched_transaction']} |
| 重复标签删除 | {report['labels_dropped_duplicate_id']} |
| 非法标签值删除 | {report['labels_dropped_invalid_value']} |

## 执行规则

1. 账户唯一键为 `bank_id + account_number`；空键与重复键不进入清洗结果。
2. 交易必须具备交易 ID、时间、付款方、收款方、双边金额、币种和支付方式；时间统一为 ISO 8601，金额保留源数据的有效精度，避免小额交易被舍入为零。
3. 交易 ID 或完整业务载荷重复时，仅保留第一条记录。
4. 自转交易可能代表再投资等合法业务，保留供规则引擎结合上下文判断。
5. 所有交易关联账户必须存在；账户元数据缺失时创建 `referenced_only` 占位账户，避免图谱断链。
6. `labels.csv` 仅用于离线评估，任何规则、图谱、风险评分和 Agent 均不得读取其字段。
"""


def clean_dataset(input_dir: Path, output_dir: Path, report_path: Path) -> dict[str, int]:
    report: dict[str, int] = Counter()
    account_rows = read_rows(input_dir / "accounts.csv")
    transaction_rows = read_rows(input_dir / "transactions.csv")
    label_rows = read_rows(input_dir / "labels.csv")
    case_rows = read_rows(input_dir / "cases.csv")
    report["accounts_input"] = len(account_rows)
    report["transactions_input"] = len(transaction_rows)

    accounts = clean_accounts(account_rows, report)
    transactions = clean_transactions(transaction_rows, report)
    add_missing_accounts(accounts, transactions, report)
    labels = clean_labels(label_rows, {row["transaction_id"] for row in transactions}, report)
    cases = [{field: normalize_text(row.get(field)) for field in CASE_FIELDS} for row in case_rows]
    report["accounts_output"] = len(accounts)
    report["transactions_output"] = len(transactions)
    report["labels_output"] = len(labels)
    report["cases_output"] = len(cases)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_rows(output_dir / "accounts.csv", ACCOUNT_FIELDS, accounts)
    write_rows(output_dir / "transactions.csv", TRANSACTION_FIELDS, transactions)
    write_rows(output_dir / "labels.csv", LABEL_FIELDS, labels)
    write_rows(output_dir / "cases.csv", CASE_FIELDS, cases)
    (output_dir / "data_quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_markdown(report), encoding="utf-8")
    return dict(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean AML CSV files into an analysis-ready dataset.")
    parser.add_argument("--input-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/cleaned"))
    parser.add_argument("--report-path", type=Path, default=Path("docs/data-cleaning-report.md"))
    args = parser.parse_args()
    print(json.dumps(clean_dataset(args.input_dir, args.output_dir, args.report_path), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
