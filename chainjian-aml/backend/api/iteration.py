"""Self-iteration diagnostics and proposal endpoints."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from scripts.iteration_cycle import run_cycle
from monitoring.service import latest_snapshot
from core.warehouse import DEFAULT_DATABASE

router = APIRouter(tags=["iteration"])
PROPOSAL_DIR = PROJECT_ROOT / "docs" / "operations" / "iteration-proposals"


def _proposal_items() -> list[dict]:
    items = []
    for path in sorted(PROPOSAL_DIR.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append({
                "run_id": payload.get("run_id", path.stem),
                "created_at": payload.get("monitoring", {}).get("snapshot_at"),
                "signals": payload.get("signals", []),
                "evaluation": payload.get("evaluation", {}),
                "proposal_path": payload.get("proposal_path", str(path.with_suffix(".md"))),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return items


@router.get("/iteration/status")
def iteration_status() -> dict:
    """Return the latest persisted diagnostic state for the workbench."""
    snapshot = latest_snapshot(DEFAULT_DATABASE)
    proposals = _proposal_items()
    latest = proposals[0] if proposals else None
    signals = (latest or {}).get("signals", [])
    red = sum(1 for item in signals if item.get("level") == "RED")
    yellow = sum(1 for item in signals if item.get("level") == "YELLOW")
    return {
        "stage": "monitor_evaluate_diagnose_propose",
        "stage_label": "第一阶段：监控、评估、诊断、提案",
        "automation_boundary": "自动生成诊断和提案；规则、权重、模型和发布仍需人工审批",
        "snapshot": snapshot,
        "latest_proposal": latest,
        "proposal_count": len(proposals),
        "signals_summary": {"red": red, "yellow": yellow, "total": len(signals)},
        "proposals": proposals[:10],
    }


@router.post("/iteration/run")
def run_iteration() -> dict:
    """Run one monitored iteration cycle and persist a reviewable proposal."""
    try:
        result = run_cycle(DEFAULT_DATABASE, PROPOSAL_DIR)
    except Exception as error:  # surface a stable API error to the workbench
        raise HTTPException(status_code=500, detail=f"自迭代诊断失败：{error}") from error
    return {
        "run_id": result["run_id"],
        "snapshot": result["monitoring"],
        "evaluation": result["evaluation"],
        "signals": result["signals"],
        "proposal_path": result["proposal_path"],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
