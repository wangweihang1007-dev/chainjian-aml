"""Compliance research and review-only SAR draft endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from legal_research.reference_index import get_legal_basis, search_references
from sar.orchestrator import build_sar_draft
from agent.tools import get_alert_detail

router = APIRouter(tags=["compliance-research"])


@router.get("/legal/search")
def legal_search(query: str = Query(min_length=2), limit: int = Query(default=5, ge=1, le=20)) -> dict:
    return {"query": query, "results": search_references(query, limit), "verification_required": True}


@router.get("/alerts/{alert_id}/legal-basis")
def alert_legal_basis(alert_id: str) -> dict:
    alert = get_alert_detail(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert not found: {alert_id}")
    return {"alert_id": alert_id, "references": get_legal_basis(alert.get("rule_hits", [])), "verification_required": True}


@router.get("/alerts/{alert_id}/sar-draft")
def sar_draft(alert_id: str) -> dict:
    try:
        return build_sar_draft(alert_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"SAR draft unavailable: {error}") from error
