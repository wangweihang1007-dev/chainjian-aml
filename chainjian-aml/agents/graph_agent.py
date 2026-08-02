"""Neo4j-backed graph investigation agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.tools import get_transaction_path
from core.warehouse import DEFAULT_DATABASE


class GraphAgent:
    name = "Graph Agent"

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def run(self, account_id: str) -> dict[str, Any]:
        paths = get_transaction_path(account_id, max_hops=3)
        suspicious_nodes = sorted({node for path in paths for node in path.get("account_path", [])[1:]})
        cycles = [path for path in paths if path.get("account_path", [])[0:1] == path.get("account_path", [])[ -1:]]
        return {"account_id": account_id, "paths": paths, "suspicious_nodes": suspicious_nodes, "cycles": cycles}
