"""FastAPI endpoint for grounded AML investigations."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent
from agent.adjudicator import AdjudicationAgent
from agents.supervisor_agent import SupervisorAgent


router = APIRouter(tags=["investigation-agent"])


class InvestigationRequest(BaseModel):
    user_input: str


@router.post("/agent/investigate")
def investigate(request: InvestigationRequest) -> dict:
    """Investigate an alert ID embedded in user input, e.g. '分析 AL000001'."""
    try:
        return InvestigationAgent().run(request.user_input)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/agent/adjudicate/{alert_id}")
def adjudicate(alert_id: str) -> dict:
    """Return structured second-stage KEEP/DISCARD advice without mutating the alert."""
    try:
        return AdjudicationAgent().adjudicate(alert_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/agent/investigate/{alert_id}/trace")
def investigation_trace(alert_id: str) -> dict:
    return {"alert_id": alert_id, "trace": InvestigationAgent().get_trace(alert_id)}


@router.post("/agent/multi-investigate")
def multi_investigate(request: InvestigationRequest) -> dict:
    """Run the dynamic multi-agent investigation workflow."""
    try:
        return SupervisorAgent().run(request.user_input)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/agent/multi-investigate/{alert_id}/tasks")
def multi_investigation_tasks(alert_id: str) -> dict:
    return {"alert_id": alert_id, "tasks": SupervisorAgent().get_tasks(alert_id)}
