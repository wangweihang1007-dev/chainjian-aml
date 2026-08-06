"""Neo4j-backed graph investigation agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools import get_transaction_path
from core.warehouse import DEFAULT_DATABASE
from core.neo4j_client import run_read


class GraphAgent:
    name = "Graph Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def run(self, account_id: str) -> dict[str, Any]:
        paths = get_transaction_path(account_id, max_hops=3, warehouse_path=self.warehouse_path)
        suspicious_nodes = sorted({node for path in paths for node in path.get("account_path", [])[1:]})
        cycles = []
        query = """
        MATCH path = (source:Account {account_id: $account_id})-[:TRANSFER*3..8]->(source)
        RETURN [node IN nodes(path) | node.account_id] AS account_path,
               [transfer IN relationships(path) | {transaction_id: transfer.transaction_id,
                timestamp: transfer.timestamp, amount_paid: transfer.amount_paid,
                payment_currency: transfer.payment_currency}] AS transfers
        LIMIT 20
        """
        degraded = False
        try:
            cycle_rows = run_read(query, {"account_id": account_id})
        except Exception:
            cycle_rows = []
            degraded = True
        for row in cycle_rows:
            cycles.append(self._serialize(row))
        return {"account_id": account_id, "paths": paths, "suspicious_nodes": suspicious_nodes, "cycles": cycles,
                "data_source": "SQLite fallback" if degraded else "Neo4j / SQLite path service", "degraded": degraded}

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, list):
                return [normalize(item) for item in value]
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            return value.to_native().isoformat() if hasattr(value, "to_native") else value
        return normalize(row)
