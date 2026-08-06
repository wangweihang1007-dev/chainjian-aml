"""Read-only tools used by the AML investigation agent."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.database import sqlite3
from app.alert_service import AlertService
from core.neo4j_client import run_read
from core.warehouse import DEFAULT_DATABASE
from risk_profile.profile_service import AccountProfileService


def get_alert_detail(alert_id: str, warehouse_path: Path = DEFAULT_DATABASE) -> dict[str, Any] | None:
    alert = AlertService(warehouse_path).get_alert(alert_id)
    return alert.as_dict() if alert else None


def get_transaction_path(account_id: str, max_hops: int = 3, limit: int = 30, warehouse_path: Path = DEFAULT_DATABASE) -> list[dict[str, Any]]:
    """Return graph paths, with a deterministic PostgreSQL one-hop fallback."""
    if not 1 <= max_hops <= 3:
        raise ValueError("max_hops must be between 1 and 3")
    query = f"""
    MATCH path = (source:Account {{account_id: $account_id}})-[:TRANSFER*1..{max_hops}]-(target:Account)
    WHERE source <> target
    RETURN [node IN nodes(path) | node.account_id] AS account_path,
           [transfer IN relationships(path) | {{
               transaction_id: transfer.transaction_id,
               timestamp: transfer.timestamp,
               amount_paid: transfer.amount_paid,
               payment_currency: transfer.payment_currency
           }}] AS transfers
    LIMIT $limit
    """
    try:
        rows = run_read(query, {"account_id": account_id, "limit": limit * 3})
        # The relational fallback returns the full transfer projection. Apply
        # the account predicate here because the fallback SQL is intentionally
        # shared by all graph rules.
        if rows and "account_path" not in rows[0]:
            rows = [row for row in rows if account_id in {row.get("source_account_id"), row.get("target_account_id")}]
        return _unique_paths(rows, limit)
    except Exception:
        return _sqlite_transaction_paths(account_id, limit, warehouse_path)


def _unique_paths(rows: Any, limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        item = _serialize_temporal(row)
        # ``run_read`` returns the canonical transfer projection when Neo4j is
        # unavailable. Convert that projection to the path shape expected by
        # the graph API instead of silently dropping every fallback row.
        if not item.get("account_path") and item.get("source_account_id") and item.get("target_account_id"):
            item = {
                "account_path": [item["source_account_id"], item["target_account_id"]],
                "transfers": [{
                    "transaction_id": item.get("transaction_id"),
                    "timestamp": item.get("timestamp"),
                    "amount_paid": item.get("amount_paid"),
                    "payment_currency": item.get("payment_currency"),
                }],
                "source": "DWD PostgreSQL fallback",
            }
        key = tuple(item.get("account_path", []))
        if key and key not in seen:
            seen.add(key)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _sqlite_transaction_paths(account_id: str, limit: int, warehouse_path: Path = DEFAULT_DATABASE) -> list[dict[str, Any]]:
    """Use DWD facts when Neo4j is unavailable; never invent graph edges."""
    with sqlite3.connect(warehouse_path) as connection:
        rows = connection.execute(
            """SELECT transaction_id, transaction_time, amount_paid, payment_currency,
                      from_account_id, to_account_id
               FROM dwd_transaction_detail
               WHERE from_account_id = ? OR to_account_id = ?
               ORDER BY transaction_time
               LIMIT ?""",
            (account_id, account_id, limit),
        ).fetchall()
    return [{
        "account_path": [row[4], row[5]],
        "transfers": [{"transaction_id": row[0], "timestamp": row[1], "amount_paid": float(row[2]), "payment_currency": row[3]}],
        "source": "DWD PostgreSQL fallback",
    } for row in rows]


def get_transaction_evidence(alert_id: str, warehouse_path: Path = DEFAULT_DATABASE) -> list[dict[str, Any]]:
    alert = get_alert_detail(alert_id, warehouse_path)
    if not alert:
        return []
    transaction_ids = [
        transaction_id
        for evidence in alert["evidence"]
        for transaction_id in evidence["evidence_content"].get("transactions", [])
    ]
    ordered_ids = list(dict.fromkeys(transaction_ids))
    if not ordered_ids:
        return []
    placeholders = ",".join("?" for _ in ordered_ids)
    with sqlite3.connect(warehouse_path) as connection:
        rows = connection.execute(
            f"""SELECT transaction_id, transaction_time, from_account_id, to_account_id,
                       amount_paid, payment_currency, amount_received, receiving_currency, payment_format
                FROM dwd_transaction_detail WHERE transaction_id IN ({placeholders})""",
            ordered_ids,
        ).fetchall()
    results = [{
        "transaction_id": row[0], "timestamp": row[1], "from_account_id": row[2], "to_account_id": row[3],
        "amount_paid": float(row[4]), "payment_currency": row[5], "amount_received": float(row[6]),
        "receiving_currency": row[7], "payment_format": row[8],
    } for row in rows]
    positions = {transaction_id: index for index, transaction_id in enumerate(ordered_ids)}
    return sorted(results, key=lambda item: positions[item["transaction_id"]])


def get_risk_response(alert_id: str, warehouse_path: Path = DEFAULT_DATABASE) -> dict[str, Any]:
    alert = get_alert_detail(alert_id, warehouse_path)
    if not alert:
        raise ValueError(f"Alert not found: {alert_id}")
    profile = AccountProfileService(warehouse_path).get(alert["account_id"])
    rules = set(alert.get("rule_hits", []))
    reasons: list[str] = []
    recommendations: list[str] = ["加强账户监控", "人工核查资金来源和交易对手"]
    if "RAPID_MOVEMENT" in rules or "资金快进快出" in profile["risk_features"]:
        reasons.append("存在快进快出行为")
        recommendations.append("重点复核入账后短时间内的转出交易")
    if profile["counterparty_count"] >= 10:
        reasons.append("关联账户数量异常")
        recommendations.append("核查关联账户之间的业务关系和实际控制人")
    if profile["txn_count"] >= 20:
        reasons.append("交易频率较高")
    if alert["risk_level"] == "HIGH":
        recommendations.append("在人工审核完成前提高预警优先级")
    return {
        "alert_id": alert_id,
        "risk_level": alert["risk_level"],
        "recommendations": list(dict.fromkeys(recommendations)),
        "reason": list(dict.fromkeys(reasons)) or ["当前画像和命中规则未提供额外处置原因"],
        "profile": profile,
        "advisory_only": True,
        "disclaimer": "仅提供合规人员辅助建议，不自动执行冻结、限额或其他账户操作。",
    }


def _serialize_temporal(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize_temporal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_temporal(item) for item in value]
    if hasattr(value, "to_native"):
        return value.to_native().isoformat()
    return value
