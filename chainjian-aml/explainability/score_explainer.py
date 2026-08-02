"""Explain APP risk scores by deterministic rule and corroborating factors."""

from __future__ import annotations

from typing import Any

from app.risk_score import RULE_WEIGHTS


class ScoreExplainer:
    def explain(self, evidence_chain: dict[str, Any]) -> dict[str, Any]:
        alert = evidence_chain["alert"]
        total = float(alert["risk_score"])
        hits = set(alert.get("rule_hits", []))
        raw: list[dict[str, Any]] = []
        rule_raw = sum(RULE_WEIGHTS.get(rule, 0) for rule in hits)
        if rule_raw:
            raw.append({"factor": "规则命中", "raw_score": rule_raw, "reason": ", ".join(sorted(hits))})
        graph_paths = evidence_chain.get("paths", [])
        if any(len(path.get("account_path", [])) - 1 >= 3 for path in graph_paths):
            raw.append({"factor": "图谱风险", "raw_score": 30, "reason": "存在 3 跳资金路径"})
        if any(item["type"] == "cycle_transaction" for item in evidence_chain.get("evidence", [])):
            raw.append({"factor": "图谱风险", "raw_score": 30, "reason": "存在资金回流路径"})
        profile = evidence_chain.get("account_profile", {})
        if any(item["type"] == "rapid_movement" for item in evidence_chain.get("evidence", [])) or "资金快进快出" in profile.get("risk_features", []):
            raw.append({"factor": "交易行为", "raw_score": 15, "reason": "资金快速转移"})
        if "高频交易" in profile.get("risk_features", []) or profile.get("txn_count", 0) >= 20:
            raw.append({"factor": "账户画像", "raw_score": 5, "reason": "账户高频交易"})
        raw_total = sum(item["raw_score"] for item in raw)
        if raw_total < total:
            raw.append({"factor": "Alert 其他配置", "raw_score": total - raw_total, "reason": "APP Alert 保存的风险评分与可解释因子之间的差额"})
            raw_total = total
        scale = min(1.0, total / raw_total) if raw_total else 0.0
        breakdown = [{"factor": item["factor"], "score": round(item["raw_score"] * scale, 2), "raw_score": item["raw_score"], "reason": item["reason"]} for item in raw]
        if breakdown:
            residual = round(total - sum(item["score"] for item in breakdown), 2)
            breakdown[-1]["score"] = round(breakdown[-1]["score"] + residual, 2)
        return {"total_score": total, "score_breakdown": breakdown, "raw_score": raw_total, "method": "规则权重与真实证据因子按比例归一到 APP risk_score"}
