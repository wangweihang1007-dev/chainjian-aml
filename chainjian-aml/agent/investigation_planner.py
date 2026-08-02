"""Rule- and profile-driven investigation planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InvestigationStep:
    step_id: str
    step_name: str
    tool_name: str
    input: dict[str, Any]
    status: str = "WAITING"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_plan(alert: dict[str, Any], profile: dict[str, Any]) -> list[InvestigationStep]:
    """Select only tools relevant to the alert's rules and account features."""
    rule_hits = set(alert.get("rule_hits", []))
    features = set(profile.get("risk_features", []))
    account_id = alert["account_id"]
    alert_id = alert["alert_id"]
    plan = [
        InvestigationStep("S01", "查询预警详情", "get_alert_detail", {"alert_id": alert_id}),
        InvestigationStep("S02", "查询账户风险画像", "get_account_profile", {"account_id": account_id}),
    ]
    if alert.get("risk_level") == "HIGH" or rule_hits & {"CYCLE_TRANSFER", "FAN_IN_COLLECTION", "MULTI_HOP_TRANSFER"}:
        plan.append(InvestigationStep("S03", "查询1-3跳资金路径", "get_transaction_path", {"account_id": account_id, "max_hops": 3}))
    if "CYCLE_TRANSFER" in rule_hits:
        plan.append(InvestigationStep("S04", "检查循环交易", "check_cycle_evidence", {"alert_id": alert_id}))
    if "RAPID_MOVEMENT" in rule_hits or "资金快进快出" in features:
        plan.append(InvestigationStep("S05", "检查快进快出", "check_rapid_movement", {"alert_id": alert_id, "account_id": account_id}))
    if rule_hits or alert.get("risk_level") in {"HIGH", "MEDIUM"}:
        plan.append(InvestigationStep("S06", "查询关键交易证据", "get_transaction_evidence", {"alert_id": alert_id}))
    plan.extend([
        InvestigationStep("S07", "生成风险结论", "build_risk_conclusion", {"alert_id": alert_id}),
        InvestigationStep("S08", "生成处置建议", "get_risk_response", {"alert_id": alert_id}),
        InvestigationStep("S09", "生成调查报告", "generate_report", {"alert_id": alert_id}),
    ])
    return plan
