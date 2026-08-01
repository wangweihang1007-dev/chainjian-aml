"""Convert graph paths into frontend-neutral nodes and edges."""

from __future__ import annotations


def path_payload(paths: list[dict]) -> dict[str, list[dict]]:
    """Build a deduplicated graph payload without exposing evaluation labels."""
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for path in paths:
        for account_id in path["account_path"]:
            nodes[account_id] = {"id": account_id, "label": account_id, "type": "account"}
        for source, target, transfer in zip(path["account_path"], path["account_path"][1:], path["transfers"]):
            transaction_id = transfer["transaction_id"]
            edges[transaction_id] = {
                "id": transaction_id, "source": source, "target": target,
                "amount_paid": transfer["amount_paid"], "currency": transfer["payment_currency"],
                "timestamp": transfer["timestamp"],
            }
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}
