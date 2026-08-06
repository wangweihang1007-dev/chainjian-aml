"""Operational AML monitoring endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter, Query

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from monitoring.service import collect_metrics

router = APIRouter(tags=["monitoring"])


@router.get("/monitoring/metrics")
def monitoring_metrics(quality_mode: str = Query("balanced", pattern="^(balanced|precision80)$")) -> dict:
    # The dashboard must reflect the current SQLite warehouse, not an old cached snapshot.
    return collect_metrics(quality_mode=quality_mode)
