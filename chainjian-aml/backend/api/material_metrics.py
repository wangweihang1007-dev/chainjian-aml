"""Material-review metrics and judge-friendly demo scenario endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.alert_service import AlertService
from core.warehouse import DEFAULT_DATABASE
from material_review.service import create_demo_materials, metrics

router = APIRouter(tags=["material-metrics"])


@router.get("/materials/metrics")
def material_metrics() -> dict:
    return metrics()


@router.post("/alerts/{alert_id}/materials/demo-case")
def demo_case(alert_id: str) -> dict:
    alert = AlertService(DEFAULT_DATABASE).get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="案件不存在")
    return {"alert_id": alert_id, "materials": create_demo_materials(alert_id, alert.account_id)}
