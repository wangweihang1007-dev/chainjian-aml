"""Backend API access for the Streamlit review workbench."""

from __future__ import annotations

from typing import Any

try:
    from .api_client import path_id, request_json
except ImportError:  # Streamlit executes page modules with frontend on sys.path.
    from api_client import path_id, request_json


def dashboard_data() -> dict[str, Any]:
    data = request_json("/dashboard/summary")
    data["top_accounts"] = [tuple(item) for item in data.get("top_accounts", [])]
    return data


def list_alerts(risk_level: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    alerts = request_json("/alerts")
    return [alert for alert in alerts if (risk_level in (None, "全部", "鍏ㄩ儴") or alert["risk_level"] == risk_level) and (status in (None, "全部", "鍏ㄩ儴") or alert["status"] == status)]


def alert_detail(alert_id: str) -> dict[str, Any] | None:
    try:
        return request_json(f"/alerts/{path_id(alert_id)}")
    except Exception:
        return None


def graph_intelligence(alert_id: str, max_hops: int = 3) -> dict[str, Any]:
    return request_json(f"/alerts/{path_id(alert_id)}/graph-intelligence?max_hops={max_hops}")


def account_profile(account_id: str) -> dict[str, Any]:
    return request_json(f"/accounts/{path_id(account_id)}/profile")


def transaction_paths(account_id: str, max_hops: int = 3) -> list[dict[str, Any]]:
    data = request_json(f"/graph/{path_id(account_id)}?max_hops={max_hops}")
    return data.get("paths", [])


def risk_response(alert_id: str) -> dict[str, Any]:
    return request_json(f"/alerts/{path_id(alert_id)}/risk-response")


def transaction_evidence(alert_id: str) -> list[dict[str, Any]]:
    return request_json(f"/alerts/{path_id(alert_id)}/transaction-evidence").get("transactions", [])


def review_pending() -> list[dict[str, Any]]:
    return request_json("/reviews/pending")


def submit_review(alert_id: str, reviewer: str, action: str, comment: str) -> dict[str, Any]:
    return request_json(f"/alerts/{path_id(alert_id)}/review", "POST", {"reviewer": reviewer, "action": action, "comment": comment})


def review_history(alert_id: str) -> dict[str, Any]:
    return request_json(f"/alerts/{path_id(alert_id)}/reviews")
