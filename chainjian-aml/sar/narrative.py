"""Grounded SAR narrative draft renderer."""

from __future__ import annotations

from typing import Any

from .privacy_guard import mask_identifier, stable_subject_id


def render_narrative(alert: dict[str, Any], evidence: list[dict[str, Any]], legal_basis: list[dict[str, Any]], judgment: dict[str, Any]) -> str:
    account = str(alert.get("account_id", ""))
    transactions = "\n".join(
        f"- {item.get('transaction_id', 'UNKNOWN')}：{item.get('timestamp', 'UNKNOWN')}，"
        f"{item.get('amount_paid', 'UNKNOWN')} {item.get('payment_currency', '')}，"
        f"{mask_identifier(item.get('from_account_id', ''))} → {mask_identifier(item.get('to_account_id', ''))}"
        for item in evidence[:30]
    ) or "- 当前没有可引用的交易证据。"
    citations = "\n".join(f"- {item['citation']}（关联规则：{item.get('linked_rule', '案件')}; 需核验）" for item in legal_basis) or "- 当前没有命中本地参考资料，需人工补充依据。"
    return f"""# SAR 可疑交易报告草案

## 1. 报告状态

- 草案编号：{stable_subject_id(alert.get('alert_id', ''))}
- 案件编号：{alert.get('alert_id', 'UNKNOWN')}
- 主体标识：{stable_subject_id(account)}
- 报告判定：{judgment['decision']}
- 提交状态：不可直接报送，必须经过授权合规人员审核

## 2. 可疑行为摘要

- 风险等级：{alert.get('risk_level', 'UNKNOWN')}
- 风险评分：{alert.get('risk_score', 'UNKNOWN')}
- 命中规则：{', '.join(alert.get('rule_hits', [])) or 'UNKNOWN'}
- 风险账户：{mask_identifier(account)}

## 3. 事实交易证据

{transactions}

## 4. 法律/规则参考

{citations}

## 5. 审核事项

- 核验客户身份、交易背景、资金来源和交易对手关系；
- 核验本地参考资料的现行有效性、适用主体和具体报送要素；
- 由授权审核人员确认是否形成正式可疑交易报告；
- 保留分析过程、引用证据、审核意见和版本信息。

> 本文是基于当前案件数据生成的内部审核草案，不是正式 SAR，不自动提交监管系统。法律引用来自仓库本地参考资料，使用前必须由专业人员核验。
"""
