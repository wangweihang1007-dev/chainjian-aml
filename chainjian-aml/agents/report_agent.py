"""Evidence-grounded report aggregation agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent.report_generator import generate_report
from core.warehouse import DEFAULT_DATABASE


class ReportAgent:
    name = "Report Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm: Callable[[str, dict[str, Any]], str] | None = None) -> None:
        self.warehouse_path = warehouse_path
        self.llm = llm

    def run(self, data: dict[str, Any]) -> dict[str, Any]:
        report = generate_report(data, self.llm)
        return {"report": report, "evidence_sources": [key for key in ("rule_analysis", "graph_analysis", "transaction_analysis", "transaction_evidence") if key in data]}
