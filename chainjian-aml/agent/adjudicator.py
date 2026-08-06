"""Evidence-grounded second-stage alert adjudication agent.

The adjudicator is advisory by default. It never reads evaluation labels and
does not mutate alert status; a separate offline gate decides whether it may
be enabled for automatic filtering.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from agent.llm_client import configured_llm, llm_status
from agent.tools import get_alert_detail, get_transaction_evidence
from core.warehouse import DEFAULT_DATABASE


PROMPT = """你是反洗钱预警二次复核智能体。只能根据输入中的 alert 和 evidence 判断，不能补造事实。
只输出一个 JSON 对象，字段必须为 decision（KEEP 或 DISCARD）、confidence（0 到 1）、reasons（字符串数组）、evidence_ids（输入中存在的交易 ID 数组）。
证据不足时 decision=KEEP，confidence 不超过 0.55，并说明需要人工复核。"""


class AdjudicationAgent:
    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, llm: Callable[[str, dict[str, Any]], str] | None = None) -> None:
        self.warehouse_path = warehouse_path
        self.llm = llm if llm is not None else configured_llm()[1]

    def adjudicate(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        evidence = get_transaction_evidence(alert_id, self.warehouse_path)
        payload = {"alert": alert, "evidence": evidence}
        if self.llm:
            try:
                result = self._parse(self.llm(PROMPT, payload), {str(item["transaction_id"]) for item in evidence})
                return {**result, "alert_id": alert_id, "mode": "llm", "ai": llm_status()}
            except Exception:
                pass
        return {**self._deterministic(alert, evidence), "alert_id": alert_id, "mode": "deterministic_fallback", "ai": llm_status()}

    @staticmethod
    def _deterministic(alert: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        rules = set(alert.get("rule_hits", [])); ids = [str(item["transaction_id"]) for item in evidence]
        reasons = []
        if "CYCLE_TRANSFER" in rules:
            reasons.append("存在闭环资金路径")
        if "LAYERED_FLOW" in rules:
            reasons.append("存在多层资金分散后归集路径")
        if len(ids) >= 5:
            reasons.append(f"预警证据包含 {len(ids)} 笔关联交易")
        confidence = min(0.95, 0.55 + 0.08 * len(reasons) + (0.12 if alert.get("risk_level") == "HIGH" else 0))
        return {"decision": "KEEP", "confidence": round(confidence, 2), "reasons": reasons or ["规则已命中，需人工复核"], "evidence_ids": ids}

    @staticmethod
    def _parse(raw: str, valid_ids: set[str]) -> dict[str, Any]:
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("adjudicator did not return JSON")
        result = json.loads(match.group(0))
        if result.get("decision") not in {"KEEP", "DISCARD"}:
            raise ValueError("invalid decision")
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
        result["reasons"] = [str(item) for item in result.get("reasons", [])][:8]
        result["evidence_ids"] = [str(item) for item in result.get("evidence_ids", []) if str(item) in valid_ids]
        return result
