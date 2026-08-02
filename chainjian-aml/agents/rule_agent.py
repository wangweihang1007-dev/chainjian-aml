"""Rule-focused investigation agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools import get_alert_detail
from core.warehouse import DEFAULT_DATABASE


RULE_EXPLANATIONS = {
    "CYCLE_TRANSFER": "规则命中循环资金回流，需要核查闭环路径和交易时间顺序。",
    "RAPID_MOVEMENT": "规则命中快进快出，需要核查入账后短时间内的转出。",
    "FAN_IN_COLLECTION": "规则命中资金归集，需要核查多个对手方流向同一账户。",
    "MULTI_HOP_TRANSFER": "规则命中多跳转移，需要核查超过一跳的资金路径。",
}


class RuleAgent:
    name = "Rule Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def run(self, alert_id: str) -> dict[str, Any]:
        alert = get_alert_detail(alert_id, self.warehouse_path)
        if not alert:
            raise ValueError(f"Alert not found: {alert_id}")
        hits = list(alert.get("rule_hits", []))
        explanations = [RULE_EXPLANATIONS.get(hit, f"规则 {hit} 已在预警记录中命中，具体条件以规则配置为准。") for hit in hits]
        return {"alert_id": alert_id, "rule_hits": hits, "explanation": " ".join(explanations), "risk_level": alert["risk_level"], "risk_score": alert["risk_score"]}
