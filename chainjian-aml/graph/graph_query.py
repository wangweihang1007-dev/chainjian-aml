"""Read-only Neo4j graph-query facade shared by APIs and UI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.tools import get_transaction_path


def get_account_paths(account_id: str, max_hops: int = 3) -> list[dict]:
    """Return deduplicated 1–3 hop outbound transfer paths."""
    return get_transaction_path(account_id, max_hops=max_hops)
