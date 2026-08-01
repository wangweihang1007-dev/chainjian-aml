"""Read-only transaction-graph endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from graph.graph_query import get_account_paths
from graph.visualization import path_payload

router = APIRouter(tags=["graph"])


@router.get("/graph/{account_id}")
def account_graph(account_id: str, max_hops: int = Query(default=3, ge=1, le=3)) -> dict:
    try:
        paths = get_account_paths(account_id, max_hops)
        return {"account_id": account_id, "max_hops": max_hops, "paths": paths, "graph": path_payload(paths)}
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Graph query unavailable: {error}") from error
