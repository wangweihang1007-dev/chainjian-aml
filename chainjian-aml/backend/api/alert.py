"""FastAPI endpoints for APP-layer AML alert cases."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.alert_service import AlertService
from app.review_service import ReviewService
from core.warehouse import DEFAULT_DATABASE
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from counterfactual.analyzer import CounterfactualAnalyzer
from agent.tools import get_risk_response, get_transaction_evidence
from risk_profile.profile_service import AccountProfileService
from rules.rule_engine import RuleEngine
from api.auth import current_user


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


@router.get("/reviews/pending")
def pending_reviews() -> list[dict]:
    return [alert.as_dict() for alert in review_service().pending_alerts()]


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: str) -> dict:
    alert = service().get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert.as_dict()


@router.get("/alerts/{alert_id}/explainability")
def explain_alert(alert_id: str) -> dict:
    """Return the evidence chain and deterministic score explanation."""
    try:
        chain = EvidenceBuilder(DEFAULT_DATABASE).build(alert_id)
        return {"alert_id": alert_id, "evidence_chain": chain, "risk_explanation": RiskExplainer().explain(chain), "score_explanation": ScoreExplainer().explain(chain)}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/alerts/{alert_id}/counterfactual")
def counterfactual_alert(alert_id: str) -> dict:
    """Return read-only risk simulations for evidence factors."""
    try:
        return CounterfactualAnalyzer(DEFAULT_DATABASE).analyze(alert_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/alerts/{alert_id}/risk-response")
def alert_risk_response(alert_id: str) -> dict:
    try:
        return get_risk_response(alert_id, DEFAULT_DATABASE)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/alerts/{alert_id}/transaction-evidence")
def alert_transaction_evidence(alert_id: str) -> dict:
    if not service().get_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"alert_id": alert_id, "transactions": get_transaction_evidence(alert_id, DEFAULT_DATABASE)}


@router.get("/accounts/{account_id}/profile")
def account_profile(account_id: str) -> dict:
    return AccountProfileService(DEFAULT_DATABASE).get(account_id)


@router.post("/alerts/{alert_id}/review")
def submit_review(alert_id: str, request: ReviewRequest, authorization: str | None = Header(default=None)) -> dict:
    try:
        if request.action.upper() not in {"CONFIRM", "REJECT", "NEED_MORE_INFO"} or not request.reviewer.strip() or not request.comment.strip():
            review_service().submit_review(alert_id, request.reviewer, request.action, request.comment)
        user = current_user(authorization)
        if not user:
            raise HTTPException(status_code=401, detail="请先登录审核账号")
        if user["username"] != request.reviewer.strip():
            raise HTTPException(status_code=403, detail="审核人必须与当前登录账号一致")
        review = review_service().submit_review(alert_id, user["username"], request.action, request.comment)
        return review.as_dict()
    except ValueError as error:
        raise HTTPException(status_code=400 if any(field in str(error) for field in ("action", "reviewer", "comment")) else 404, detail=str(error)) from error


@router.get("/alerts/{alert_id}/reviews")
def review_history(alert_id: str) -> dict:
    if not service().get_alert(alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return review_service().review_history(alert_id)
