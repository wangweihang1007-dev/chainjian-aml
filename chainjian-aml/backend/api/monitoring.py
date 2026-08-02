"""Operational AML monitoring endpoints."""

import sys
from pathlib import Path

from fastapi import APIRouter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from monitoring.service import collect_metrics, latest_snapshot

router = APIRouter(tags=["monitoring"])


@router.get("/monitoring/metrics")
def monitoring_metrics() -> dict:
    return latest_snapshot() or collect_metrics()
