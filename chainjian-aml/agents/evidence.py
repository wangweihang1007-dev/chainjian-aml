"""Shared, auditable evidence primitives for multi-agent investigations."""

from __future__ import annotations

from typing import Any


def evidence_item(
    source: str,
    evidence_type: str,
    description: str,
    evidence_ids: list[str] | None = None,
    *,
    data_source: str = "SQLite warehouse",
    confidence: float = 1.0,
    degraded: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "evidence_type": evidence_type,
        "description": description,
        "evidence_ids": [str(item) for item in (evidence_ids or [])],
        "data_source": data_source,
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "degraded": bool(degraded),
    }


def build_evidence_index(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert specialist output into one stable evidence blackboard."""
    items: list[dict[str, Any]] = []
    rule = outputs.get("rule_analysis") or {}
    if rule:
        items.append(evidence_item("Rule Agent", "rule_hit", "预警记录中的规则命中", rule.get("rule_hits", [])))
    transaction = outputs.get("transaction_analysis") or {}
    if transaction:
        ids = transaction.get("key_transaction_ids", [])
        items.append(evidence_item("Transaction Agent", "transaction_behavior", "账户交易行为与风险特征", ids, confidence=0.9))
    graph = outputs.get("graph_analysis") or {}
    if graph:
        path_ids = [tx.get("transaction_id") for path in graph.get("paths", []) for tx in path.get("transactions", []) if isinstance(tx, dict)]
        items.append(evidence_item("Graph Agent", "fund_flow_path", "账户资金路径和关联节点", path_ids, data_source=graph.get("data_source", "Neo4j / SQLite fallback"), degraded=bool(graph.get("degraded"))))
        if graph.get("cycles"):
            items.append(evidence_item("Graph Agent", "cycle_path", "发现循环资金路径", [tx.get("transaction_id") for cycle in graph["cycles"] for tx in cycle.get("transfers", []) if isinstance(tx, dict)]))
    return items
