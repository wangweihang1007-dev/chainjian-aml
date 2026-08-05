"""Supplementary case-material review endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from material_review.service import decide_material, list_materials, review_material
from app.alert_service import AlertService
from core.warehouse import DEFAULT_DATABASE
from agent.tools import get_transaction_evidence

router = APIRouter(tags=["supplementary-materials"])


@router.get("/alerts/{alert_id}/materials")
def get_materials(alert_id: str) -> dict:
    materials = list_materials(alert_id)
    return {"alert_id": alert_id, "materials": materials, "summary": {"total": len(materials), "human_review": sum(item["review_route"] == "human_review" for item in materials)}}


@router.post("/alerts/{alert_id}/materials")
async def upload_material(alert_id: str, file: UploadFile = File(...), material_type: str = Form("other")) -> dict:
    try:
        alert = AlertService(DEFAULT_DATABASE).get_alert(alert_id)
        if not alert:
            raise ValueError("案件不存在")
        try:
            evidence = get_transaction_evidence(alert_id, DEFAULT_DATABASE)
        except Exception:
            evidence = []
        context = {"account_id": alert.account_id, "transaction_amounts": [item.get("amount_paid") or item.get("amount") for item in evidence]}
        result = review_material(alert_id, file.filename or "material", await file.read(), file.content_type, context)
        result["material_type"] = material_type
        return result
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/alerts/{alert_id}/materials/{material_id}/decision")
def material_decision(alert_id: str, material_id: str, decision: str = Form(...), reviewer: str = Form("aml_ops"), note: str = Form("")) -> dict:
    try:
        return decide_material(alert_id, material_id, decision, reviewer, note)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="材料不存在") from error
