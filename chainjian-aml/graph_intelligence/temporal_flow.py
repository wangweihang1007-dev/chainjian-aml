"""Create a replayable, time-ordered view of the evidence edges."""

from __future__ import annotations

from typing import Any


def build_timeline(subgraph: dict[str, Any]) -> list[dict[str, Any]]:
    edges = sorted(subgraph.get("edges", []), key=lambda edge: (edge.get("timestamp", ""), edge.get("transaction_id", "")))
    events = []
    for index, edge in enumerate(edges, 1):
        events.append({"step": index, "transaction_id": edge["transaction_id"], "timestamp": edge["timestamp"], "from_account": edge["source"], "to_account": edge["target"], "amount": edge["amount"], "currency": edge["currency"], "evidence_type": edge["evidence_type"]})
    return events
