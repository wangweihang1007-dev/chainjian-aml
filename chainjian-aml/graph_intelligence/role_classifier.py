"""Explainable account role classification within an evidence subgraph."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from graph_intelligence.models import RoleProfile


def classify_roles(subgraph: dict[str, Any]) -> list[dict[str, Any]]:
    stats = defaultdict(lambda: {"in_count": 0, "out_count": 0, "in_amount": 0.0, "out_amount": 0.0})
    for edge in subgraph.get("edges", []):
        stats[edge["source"]]["out_count"] += 1
        stats[edge["source"]]["out_amount"] += float(edge.get("amount", 0))
        stats[edge["target"]]["in_count"] += 1
        stats[edge["target"]]["in_amount"] += float(edge.get("amount", 0))
    result = []
    for account_id, values in stats.items():
        roles: list[str] = []
        if values["in_count"] == 0 and values["out_count"] > 0:
            roles.append("source")
        if values["in_count"] >= 3 and values["in_count"] > values["out_count"]:
            roles.append("collector")
        if values["out_count"] >= 3 and values["out_count"] > values["in_count"]:
            roles.append("distributor")
        if any(edge["source"] == account_id and edge["target"] in {e["source"] for e in subgraph.get("edges", [])} for edge in subgraph.get("edges", [])):
            roles.append("bridge")
        if not roles:
            roles.append("intermediary")
        result.append(RoleProfile(account_id, roles, values["in_count"], values["out_count"], round(values["in_amount"], 2), round(values["out_amount"], 2)).as_dict())
    return sorted(result, key=lambda item: item["account_id"])
