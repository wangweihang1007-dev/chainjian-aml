"""Simulate removal of evidence factors without changing persisted data."""

from __future__ import annotations

from typing import Any


class RiskSimulator:
    def simulate(self, evidence_chain: dict[str, Any], score_explanation: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
        current = float(score_explanation.get("total_score", evidence_chain["alert"]["risk_score"]))
        breakdown = score_explanation.get("score_breakdown", [])
        candidates: list[tuple[str, str, list[str]]] = []
        for item in evidence_chain.get("evidence", []):
            if item["type"] == "cycle_transaction":
                tx_ids = [row["id"] for row in item.get("transactions", [])]
                candidates.extend((tx_id, "该交易是资金回流路径中的关键节点", ["CYCLE_TRANSFER", "资金回流路径"]) for tx_id in tx_ids)
            elif item["type"] == "rapid_movement":
                tx_ids = [row["id"] for row in item.get("transactions", [])]
                candidates.extend((tx_id, "该交易参与预警记录的快速资金转移", ["RAPID_MOVEMENT", "资金快速转移"]) for tx_id in tx_ids)
        for rule in evidence_chain["alert"].get("rule_hits", []):
            candidates.append((rule, f"移除规则因子 {rule} 的模拟贡献", [rule]))
        seen: set[str] = set()
        results = []
        for factor, explanation, markers in candidates:
            if factor in seen:
                continue
            seen.add(factor)
            removed = sum(float(item["score"]) for item in breakdown if any(marker in str(item.get("reason", "")) or (marker == "CYCLE_TRANSFER" and item.get("factor") == "规则命中") or (marker == "RAPID_MOVEMENT" and item.get("factor") == "规则命中") for marker in markers))
            # When rule reasons are aggregated, use the exact configured rule weight.
            if removed == 0 and factor in evidence_chain["alert"].get("rule_hits", []):
                removed = sum(float(item["score"]) for item in breakdown if item.get("factor") == "规则命中" and factor in str(item.get("reason", "")))
            after = max(0.0, round(current - removed, 2))
            results.append({"removed_factor": factor, "score_before": current, "score_after_removal": after, "impact": round(current - after, 2), "explanation": explanation, "evidence_transaction_ids": [factor] if factor.startswith("TX") else [], "simulated": True})
        return sorted(results, key=lambda item: (-item["impact"], str(item["removed_factor"])))[:top_n]
