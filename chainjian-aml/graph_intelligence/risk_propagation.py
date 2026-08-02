"""Bounded, attributable associated-account review suggestions."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def propagate_associated_review(subgraph: dict[str, Any], direct_account_id: str, max_hops: int = 2) -> list[dict[str, Any]]:
    """Return at-most-two-hop review leads; never labels them as direct risk."""
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in subgraph.get("edges", []):
        adjacency[str(edge["source"])].append(edge)
    queue = deque([(direct_account_id, 0, [])])
    best: dict[str, dict[str, Any]] = {}
    while queue:
        account, hops, path = queue.popleft()
        if hops >= max_hops:
            continue
        for edge in adjacency.get(account, []):
            target = str(edge["target"])
            next_path = [*path, edge["transaction_id"]]
            if target == direct_account_id:
                continue
            strength = round((0.8 ** (hops + 1)) * float(edge.get("priority", 0.25)), 4)
            candidate = {"account_id": target, "classification": "associated_review", "hops": hops + 1, "path_transaction_ids": next_path, "path_strength": strength, "reason": "Only a bounded evidence path supports prioritised manual review."}
            if target not in best or strength > best[target]["path_strength"]:
                best[target] = candidate
            queue.append((target, hops + 1, next_path))
    return sorted(best.values(), key=lambda item: (-item["path_strength"], item["account_id"]))
