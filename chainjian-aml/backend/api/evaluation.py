"""Offline AML detection quality API."""

import sys
from pathlib import Path

from fastapi import APIRouter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from evaluation.evaluate_rules import evaluate_rules

router = APIRouter(tags=["evaluation"])


@router.get("/evaluation/metrics")
def get_metrics() -> dict:
    """Return offline metrics; labels are not exposed to operational rules."""
    return evaluate_rules()
