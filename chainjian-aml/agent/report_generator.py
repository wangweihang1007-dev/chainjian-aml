"""Grounded AML investigation report generation."""

from __future__ import annotations

from typing import Any, Callable

from agent.prompt import INVESTIGATION_PROMPT


def generate_report(data: dict[str, Any], llm: Callable[[str, dict[str, Any]], str] | None = None) -> str:
    """Generate a report from tool output only.

    An optional LLM callable receives the strict prompt and exact tool data.
    The default deterministic renderer is used when no approved LLM integration
    is configured, guaranteeing that no transaction fact is fabricated.
    """
    if llm:
        return llm(INVESTIGATION_PROMPT, data)
    return _render_deterministic_report(data)


def _render_deterministic_report(data: dict[str, Any]) -> str:
    alert = data["alert"]
    evidence = data["transaction_evidence"]
    paths = data["transaction_paths"]
    rule_hits = ", ".join(alert["rule_hits"]) or "无"
    path_lines = [f"- {' → '.join(path['account_path'])}" for path in paths] or ["- 未查询到 1–3 跳出向路径。"]
    evidence_lines = [
        f"| {row['transaction_id']} | {row['timestamp']} | {row['from_account_id']} | {row['to_account_id']} | {row['amount_paid']} {row['payment_currency']} |"
        for row in evidence
    ] or ["| 无 | 无 | 无 | 无 | 无 |"]
    return f"""# AML 调查报告

## 案件信息

- 案件编号：{alert['alert_id']}
- 风险账户：{alert['account_id']}
- 风险等级：{alert['risk_level']}
- 风险评分：{alert['risk_score']}
- 状态：{alert['status']}
- 命中规则：{rule_hits}
- 生成时间：{alert['created_time']}

## 资金路径（Neo4j 查询）

{chr(10).join(path_lines)}

## 关键交易证据（DWD 查询）

| 交易编号 | 时间 | 付款账户 | 收款账户 | 支付金额 |
| --- | --- | --- | --- | --- |
{chr(10).join(evidence_lines)}

## 风险解释

该报告仅依据预警命中规则、Neo4j 路径查询和 DWD 交易证据生成。当前命中规则：{rule_hits}。请结合上述路径与交易明细进行人工复核。

## 建议人工核查事项

1. 核验路径中各账户之间的业务关系与资金用途。
2. 核验关键交易的付款凭证、对手方信息及资金来源。
3. 审核人员应在系统中确认、驳回或补充调查备注后再作处置。

## 免责声明

本报告基于合成数据和系统规则生成，仅用于辅助调查与演示；不构成洗钱认定、法律意见或监管报送依据。
"""
