"""Evidence-preserving counterfactual checks for graph investigations."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _metrics(edges: list[dict[str, Any]]) -> dict[str, Any]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[str(edge["source"])].add(str(edge["target"]))

    def reaches(start: str, current: str, visited: set[str]) -> bool:
        if current == start and visited:
            return True
        if current in visited:
            return False
        visited.add(current)
        return any(reaches(start, target, visited.copy()) for target in adjacency.get(current, set()))

    closed = any(reaches(node, target, set()) for node, targets in adjacency.items() for target in targets if target != node)
    return {"edge_count": len(edges), "node_count": len({e["source"] for e in edges} | {e["target"] for e in edges}), "has_closed_loop": closed}


def analyze_counterfactual(subgraph: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
    """Remove each direct evidence edge and report the measurable impact."""
    edges = list(subgraph.get("edges", []))
    baseline = _metrics(edges)
    direct = [edge for edge in edges if edge.get("evidence_type") == "direct_hit"][:top_n]
    result = []
    for removed in direct:
        remaining = [edge for edge in edges if edge["transaction_id"] != removed["transaction_id"]]
        after = _metrics(remaining)
        impact = (baseline["edge_count"] - after["edge_count"]) + (2 if baseline["has_closed_loop"] and not after["has_closed_loop"] else 0)
        result.append({
            "transaction_id": removed["transaction_id"],
            "impact_score": impact,
            "impact_level": "HIGH" if impact >= 3 else ("MEDIUM" if impact >= 1 else "LOW"),
            "baseline": baseline,
            "after_removal": after,
            "explanation": "Removing this evidence edge changes the bounded subgraph structure." if impact else "Removing this edge does not change the bounded structure.",
        })
    return sorted(result, key=lambda item: (-item["impact_score"], item["transaction_id"]))
