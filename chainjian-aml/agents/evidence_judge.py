"""Deterministic evidence quality gate between specialists and reporting."""

from __future__ import annotations

from typing import Any


class EvidenceJudge:
    name = "Evidence Judge"

    def evaluate(self, alert: dict[str, Any], outputs: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        issues: list[str] = []
        failures = [key for key in outputs if key.endswith("_error")]
        if failures:
            issues.append(f"部分调查任务失败：{', '.join(failures)}")
        if not evidence:
            issues.append("尚未形成可回溯的结构化证据")
        if any(item.get("degraded") for item in evidence):
            issues.append("至少一个数据源处于降级模式")
        all_ids = {item_id for item in evidence for item_id in item.get("evidence_ids", [])}
        if alert.get("risk_level") == "HIGH" and not all_ids:
            issues.append("高风险案件缺少交易或资金路径证据")
        sources = {item.get("source") for item in evidence}
        coverage = round(min(1.0, len(sources) / 3), 2)
        status = "PASS" if not issues else "NEEDS_MORE_EVIDENCE"
        return {
            "status": status,
            "confidence": round(max(0.35, coverage - 0.15 * len(issues)), 2),
            "evidence_count": len(evidence),
            "evidence_id_count": len(all_ids),
            "source_coverage": sorted(source for source in sources if source),
            "issues": issues,
            "needs_more_evidence": bool(issues),
            "recommendations": ["人工核查降级数据源" if any(item.get("degraded") for item in evidence) else "补充核查交易上下文"],
        }
