"""Read-only data access for the Streamlit AML review workbench."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.alert_service import AlertService
from core.warehouse import DEFAULT_DATABASE


def dashboard_data() -> dict[str, Any]:
    with sqlite3.connect(DEFAULT_DATABASE) as connection:
        summary = connection.execute(
            "SELECT total_accounts, total_transactions FROM ads_dashboard_summary ORDER BY snapshot_at DESC LIMIT 1"
        ).fetchone() or (0, 0)
        alert_count = connection.execute("SELECT count(*) FROM alert_case").fetchone()[0]
        high_risk_accounts = connection.execute(
            "SELECT count(DISTINCT account_id) FROM alert_case WHERE risk_level = 'HIGH'"
        ).fetchone()[0]
        risk_rows = connection.execute("SELECT risk_level, count(*) FROM alert_case GROUP BY risk_level").fetchall()
        rule_rows = connection.execute("SELECT rule_hits_json FROM alert_case").fetchall()
        top_accounts = connection.execute(
            """SELECT rank.activity_rank, rank.account_id, account.entity_name, rank.total_transaction_count,
                      rank.total_transaction_amount, rank.counterparty_count
               FROM ads_account_activity_rank rank JOIN dim_account account ON account.account_id = rank.account_id
               ORDER BY rank.activity_rank LIMIT 10"""
        ).fetchall()
    risk_distribution = {level: count for level, count in risk_rows}
    rule_counts: Counter[str] = Counter()
    for (serialized_rules,) in rule_rows:
        rule_counts.update(json.loads(serialized_rules))
    return {
        "total_accounts": summary[0], "total_transactions": summary[1], "alert_count": alert_count,
        "high_risk_accounts": high_risk_accounts, "risk_distribution": risk_distribution,
        "rule_counts": dict(rule_counts), "top_accounts": top_accounts,
    }


def list_alerts(risk_level: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    alerts = AlertService(DEFAULT_DATABASE).list_alerts()
    return [
        alert.as_dict() for alert in alerts
        if (risk_level in (None, "全部") or alert.risk_level == risk_level)
        and (status in (None, "全部") or alert.status == status)
    ]


def alert_detail(alert_id: str) -> dict[str, Any] | None:
    alert = AlertService(DEFAULT_DATABASE).get_alert(alert_id)
    return alert.as_dict() if alert else None
