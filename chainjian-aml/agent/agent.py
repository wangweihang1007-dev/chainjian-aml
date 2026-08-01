"""Tool-grounded AML Investigation Agent."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from agent.report_generator import generate_report
from agent.tools import get_alert_detail, get_transaction_evidence, get_transaction_path
from core.warehouse import DEFAULT_DATABASE


class InvestigationAgent:
    """Investigate a case by orchestrating read-only evidence tools."""

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm: Callable[[str, dict[str, Any]], str] | None = None) -> None:
        self.warehouse_path = warehouse_path
        self.llm = llm

    def investigate(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        paths = get_transaction_path(alert["account_id"])
        evidence = get_transaction_evidence(alert_id, self.warehouse_path)
        data = {"alert": alert, "transaction_paths": paths, "transaction_evidence": evidence}
        return {"alert_id": alert_id, "tool_data": data, "report": generate_report(data, self.llm)}

    def run(self, user_input: str) -> dict[str, Any]:
        """Handle concise inputs such as '分析 AL000001'."""
        match = re.search(r"\bAL\d+\b", user_input.upper())
        if not match:
            raise ValueError("Please provide an alert ID, for example: 分析 AL000001")
        return self.investigate(match.group())
