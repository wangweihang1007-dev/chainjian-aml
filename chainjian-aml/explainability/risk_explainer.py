"""Deterministic risk explanations grounded in the normalized evidence chain."""

from __future__ import annotations

from typing import Any


class RiskExplainer:
    def explain(self, evidence_chain: dict[str, Any]) -> dict[str, Any]:
        alert = evidence_chain["alert"]
        reasons: list[dict[str, Any]] = []
        for item in evidence_chain.get("evidence", []):
            if item["type"] == "cycle_transaction":
                reasons.append({"reason": "循环交易", "evidence": item.get("path") or "未返回明确路径", "transaction_ids": [row["id"] for row in item.get("transactions", [])]})
            elif item["type"] == "rapid_movement":
                holding = item.get("holding_time")
                ratio = item.get("outflow_ratio")
                text = f"{holding} 分钟内转出 {float(ratio) * 100:.2f}%" if holding is not None and ratio is not None else "预警证据记录了快速转移"
                reasons.append({"reason": "快进快出", "evidence": text, "transaction_ids": [row["id"] for row in item.get("transactions", [])]})
            elif item["type"] == "graph_path":
                for path in item.get("paths", [])[:3]:
                    reasons.append({"reason": "多跳资金路径", "evidence": "->".join(path.get("account_path", [])), "transaction_ids": [row.get("transaction_id") for row in path.get("transfers", [])]})
        if not reasons and alert.get("rule_hits"):
            reasons.append({"reason": "规则命中", "evidence": ", ".join(alert["rule_hits"]), "transaction_ids": []})
        confidence = 0.92 if reasons and evidence_chain.get("transactions") else (0.75 if reasons else 0.2)
        conclusion = "账户存在" + "、".join(dict.fromkeys(item["reason"] for item in reasons)) + "行为" if reasons else "当前证据不足以形成额外风险解释"
        return {"risk_level": alert["risk_level"], "risk_score": alert["risk_score"], "conclusion": conclusion, "reasons": reasons, "confidence": confidence, "evidence_based": True}
