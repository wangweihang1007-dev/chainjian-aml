"""Case-oriented graph intelligence endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from graph_intelligence.service import GraphIntelligenceService

router = APIRouter(tags=["graph-intelligence"])


@router.get("/alerts/{alert_id}/graph-intelligence")
def alert_graph_intelligence(alert_id: str, max_hops: int = Query(default=3, ge=1, le=3)) -> dict:
    try:
        return GraphIntelligenceService().investigate(alert_id, max_hops)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Graph intelligence unavailable: {error}") from error
