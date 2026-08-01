"""Grounded investigation report endpoint."""

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent

router = APIRouter(tags=["reports"])


@router.get("/reports/{alert_id}")
def get_report(alert_id: str) -> dict:
    try:
        result = InvestigationAgent().investigate(alert_id)
        return {"alert_id": alert_id, "report_markdown": result["report"], "evidence_count": len(result["tool_data"]["transaction_evidence"])}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Report generation unavailable: {error}") from error
