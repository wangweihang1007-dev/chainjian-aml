"""Dashboard aggregate endpoint for the separated frontend."""

from __future__ import annotations

import json
from core.database import sqlite3
from collections import Counter

from fastapi import APIRouter

from core.warehouse import DEFAULT_DATABASE

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary")
def dashboard_summary() -> dict:
    with sqlite3.connect(DEFAULT_DATABASE) as connection:
        summary = connection.execute("SELECT total_accounts, total_transactions FROM ads_dashboard_summary ORDER BY snapshot_at DESC LIMIT 1").fetchone() or (0, 0)
        alert_count = connection.execute("SELECT count(*) FROM alert_case").fetchone()[0]
        high_risk = connection.execute("SELECT count(DISTINCT account_id) FROM alert_case WHERE risk_level='HIGH'").fetchone()[0]
        risk_rows = connection.execute("SELECT risk_level, count(*) FROM alert_case GROUP BY risk_level").fetchall()
        rules = connection.execute("SELECT rule_hits_json FROM alert_case").fetchall()
        top_accounts = connection.execute("""SELECT rank.activity_rank, rank.account_id, account.entity_name,
            rank.total_transaction_count, rank.total_transaction_amount, rank.counterparty_count
            FROM ads_account_activity_rank rank JOIN dim_account account ON account.account_id=rank.account_id
            ORDER BY rank.activity_rank LIMIT 10""").fetchall()
    counts: Counter[str] = Counter()
    for (serialized,) in rules:
        counts.update(json.loads(serialized))
    return {"total_accounts": summary[0], "total_transactions": summary[1], "alert_count": alert_count, "high_risk_accounts": high_risk, "risk_distribution": dict(risk_rows), "rule_counts": dict(counts), "top_accounts": top_accounts}
