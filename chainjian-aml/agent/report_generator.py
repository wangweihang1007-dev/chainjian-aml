"""Deterministic, fixed-structure AML investigation report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from agent.prompt import INVESTIGATION_PROMPT
from counterfactual.counterfactual_report import render_counterfactual_section


def generate_report(data: dict[str, Any], llm: Callable[[str, dict[str, Any]], str] | None = None) -> str:
    """Generate a report from exact tool data; the default path never invents facts."""
    if llm:
        try:
            return llm(INVESTIGATION_PROMPT, data)
        except Exception:
            # A provider outage or unsupported model must not hide the grounded report.
            pass
    return _render_deterministic_report(data)


def _render_deterministic_report(data: dict[str, Any]) -> str:
    alert = data["alert"]
    evidence = data.get("transaction_evidence", [])
    paths = data.get("transaction_paths", [])
    explainability = data.get("explainability", {})
    risk_explanation = explainability.get("risk_explanation", {})
    score_explanation = explainability.get("score_explanation", {})
    response = data.get("risk_response", {})
    generated_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reasons = [f"- {item['reason']}：{item['evidence']}" for item in risk_explanation.get("reasons", [])] or ["- 当前没有返回额外结构化原因。"]
    score_lines = [f"- {item['factor']}：+{item['score']} 分（{item['reason']}）" for item in score_explanation.get("score_breakdown", [])] or ["- 当前没有返回评分拆解。"]
    path_lines = [f"- {' → '.join(path.get('account_path', []))}" for path in paths[:20]] or ["- Neo4j 未返回资金路径。"]
    transaction_lines = [f"- {row['transaction_id']}｜金额 {row['amount_paid']} {row['payment_currency']}｜时间 {row['timestamp']}｜{row['from_account_id']} → {row['to_account_id']}" for row in evidence] or ["- 当前没有 Alert 关联交易证据。"]
    recommendation_lines = [f"- {item}" for item in response.get("recommendations", [])] or ["- 建议人工复核。"]
    counterfactual = data.get("counterfactual", {})
    counterfactual_section = render_counterfactual_section(counterfactual) if counterfactual else "## 5. 反事实分析\n\n暂无反事实结果。"
    return f"""# AML调查报告

## 1. 案件基本信息

- 案件编号：{alert['alert_id']}
- 风险账户：{alert['account_id']}
- 生成时间：{generated_time}

## 2. 风险结论

- 风险等级：{alert['risk_level']}
- 风险评分：{alert['risk_score']}
- 总体判断：{risk_explanation.get('conclusion', data.get('risk_conclusion', {}).get('conclusion', '基于当前 Alert 和已返回证据进行人工复核。'))}

## 3. 风险原因分析

{chr(10).join(reasons)}

### 风险评分组成

{chr(10).join(score_lines)}

## 4. 证据链

### 资金路径

{chr(10).join(path_lines)}

### 关键交易

{chr(10).join(transaction_lines)}

{counterfactual_section}

## 6. 人工审核建议

{chr(10).join(recommendation_lines)}
- 核查资金来源、交易对手关系和关键交易上下文。
- 结合证据链人工复核后记录确认、驳回或补充信息结论。

## 7. 免责声明

AI 输出仅作为辅助调查依据，不自动执行冻结、限额或其他账户操作，也不构成法律意见或监管申报决定。
"""
