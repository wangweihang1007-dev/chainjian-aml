"""FastAPI endpoints for APP-layer AML alert cases."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.alert_service import AlertService
from app.review_service import ReviewService
from core.warehouse import DEFAULT_DATABASE
from rules.rule_engine import RuleEngine


router = APIRouter(tags=["alerts"])


def service() -> AlertService:
    return AlertService(DEFAULT_DATABASE)


def review_service() -> ReviewService:
    return ReviewService(DEFAULT_DATABASE)


class ReviewRequest(BaseModel):
    action: str
    reviewer: str
    comment: str = ""


@router.post("/alerts/generate")
def generate_alerts() -> list[dict]:
    """Run rules against Neo4j and create or update idempotent alert cases."""
    findings = RuleEngine(DEFAULT_DATABASE).run()
    return [alert.as_dict() for alert in service().generate(findings)]


@router.get("/alerts")
def list_alerts() -> list[dict]:
    return [alert.as_dict() for alert in service().list_alerts()]


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    alert = service().get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert.as_dict()


@router.post("/alerts/{alert_id}/review")
def submit_review(alert_id: str, request: ReviewRequest) -> dict:
    try:
        review = review_service().submit_review(alert_id, request.reviewer, request.action, request.comment)
        return review.as_dict()
    except ValueError as error:
        raise HTTPException(status_code=400 if "action" in str(error) or "reviewer" in str(error) else 404, detail=str(error)) from error


@router.get("/alerts/{alert_id}/reviews")
def review_history(alert_id: str) -> dict:
    if not service().get_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return review_service().review_history(alert_id)
