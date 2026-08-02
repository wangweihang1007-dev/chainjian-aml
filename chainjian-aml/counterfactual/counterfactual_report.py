"""Markdown rendering for read-only counterfactual results."""

from __future__ import annotations

from typing import Any


def render_counterfactual_section(result: dict[str, Any]) -> str:
    lines = ["## 5. 反事实分析", "", f"当前风险评分：{result.get('current_score')}", ""]
    items = result.get("counterfactuals", [])
    if not items:
        lines.append("暂无可模拟的关键风险因素。")
    else:
        for item in items:
            lines.extend([f"- 如果移除 **{item['removed_factor']}**：{item['score_before']} → {item['score_after_removal']}（影响 {item['impact']} 分）", f"  - 说明：{item['explanation']}"])
    return "\n".join(lines)
