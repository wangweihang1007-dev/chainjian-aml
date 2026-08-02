"""Build a bounded, evidence-first subgraph for one APP alert."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from core.neo4j_client import run_read
from rules.cycle_rule import TRANSFER_QUERY

from graph_intelligence.models import GraphEdge


def build_evidence_subgraph(alert: dict[str, Any], max_hops: int = 3, max_edges: int = 60) -> dict[str, Any]:
    evidence_items = alert.get("evidence", [])
    direct_transactions = {str(tx) for item in evidence_items for tx in item.get("evidence_content", {}).get("transactions", [])}
    direct_accounts = {str(alert["account_id"])}
    for item in evidence_items:
        content = item.get("evidence_content", {})
        direct_accounts.update(str(account) for account in content.get("account_path", []))

    rows = run_read(TRANSFER_QUERY)
    normalized = []
    adjacency: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source, target = str(row["source_account_id"]), str(row["target_account_id"])
        edge = {**row, "source": source, "target": target}
        normalized.append(edge)
        adjacency[source].append(edge)

    distances = {account: 0 for account in direct_accounts}
    queue = deque(direct_accounts)
    while queue:
        account = queue.popleft()
        if distances[account] >= max_hops:
            continue
        for edge in adjacency.get(account, []):
            target = edge["target"]
            if target not in distances:
                distances[target] = distances[account] + 1
                queue.append(target)

    selected: list[GraphEdge] = []
    seen: set[str] = set()
    for edge in normalized:
        tx_id = str(edge["transaction_id"])
        is_direct = tx_id in direct_transactions
        in_scope = edge["source"] in distances and distances[edge["source"]] < max_hops
        if not is_direct and not in_scope:
            continue
        if tx_id in seen:
            continue
        seen.add(tx_id)
        evidence_type = "direct_hit" if is_direct else ("associated_review" if edge["source"] in direct_accounts or edge["target"] in direct_accounts else "context_only")
        priority = 1.0 if is_direct else (0.7 if evidence_type == "associated_review" else 0.25)
        selected.append(GraphEdge(tx_id, edge["source"], edge["target"], str(edge["timestamp"]), float(edge["amount_paid"] or 0), str(edge.get("payment_currency") or ""), evidence_type, priority))
    selected.sort(key=lambda item: (-item.priority, item.timestamp, item.transaction_id))
    selected = selected[:max_edges]
    accounts = sorted({edge.source for edge in selected} | {edge.target for edge in selected} | direct_accounts)
    return {
        "nodes": [{"account_id": account, "evidence_type": "direct_hit" if account in direct_accounts else "associated_review"} for account in accounts],
        "edges": [edge.as_dict() for edge in selected],
        "direct_transaction_ids": sorted(direct_transactions),
        "max_hops": max_hops,
    }
