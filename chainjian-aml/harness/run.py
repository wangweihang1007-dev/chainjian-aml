"""Unified, dependency-light verification harness.

Examples (run from the chainjian-aml directory):

    python -m harness.run unit
    python -m harness.run eval
    python -m harness.run all --skip-eval

The harness deliberately keeps evaluation separate from the runtime rule path.
It never changes the warehouse or production configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "harness" / "config.json"
DB = ROOT / "data" / "warehouse" / "aml.db"


def _run(name: str, command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    print(f"\n[harness] {name}: {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd, text=True)
    elapsed = round(time.perf_counter() - started, 2)
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"[harness] {status} {name} ({elapsed}s)")
    return {"name": name, "status": status, "returncode": result.returncode, "seconds": elapsed}


def unit() -> dict[str, Any]:
    return _run("python-tests", [sys.executable, "-m", "pytest", "-q"])


def compile_python() -> dict[str, Any]:
    packages = [
        "agent", "agents", "app", "backend", "counterfactual", "evaluation",
        "explainability", "graph", "graph_intelligence", "monitoring",
        "risk_profile", "rules", "sar", "scripts", "harness",
    ]
    return _run("python-compile", [sys.executable, "-m", "compileall", "-q", *packages])


def frontend() -> dict[str, Any]:
    npm = shutil.which("npm")
    if not npm:
        return {"name": "frontend-build", "status": "SKIP", "reason": "npm not found"}
    return _run("frontend-build", [npm, "run", "build"], ROOT / "web")


def smoke() -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return {"name": "api-smoke", "status": "SKIP", "reason": "node not found"}
    return _run("api-smoke", [node, "web/scripts/smoke.mjs"])


def _metric_failures(result: dict[str, Any], config: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if result.get("warning"):
        failures.append(f"evaluation warning: {result['warning']}")
    evaluation_config = config.get("evaluation", {})
    overall = result.get("overall", {})
    for metric, minimum in evaluation_config.get("overall", {}).items():
        value = overall.get(metric)
        if value is None or float(value) < float(minimum):
            failures.append(f"overall.{metric}={value!r} < {minimum}")
    for rule, thresholds in evaluation_config.get("rules", {}).items():
        actual = result.get("rules", {}).get(rule, {})
        for metric, minimum in thresholds.items():
            value = actual.get(metric)
            if value is None or float(value) < float(minimum):
                failures.append(f"rules.{rule}.{metric}={value!r} < {minimum}")
    return failures


def evaluation() -> dict[str, Any]:
    if not DB.exists():
        print(f"[harness] FAIL evaluation: database not found: {DB}")
        return {"name": "evaluation-gate", "status": "FAIL", "reason": "database not found"}
    sys.path.insert(0, str(ROOT))
    from evaluation.evaluate_rules import evaluate_rules

    result = evaluate_rules(DB)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    failures = _metric_failures(result, config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        print("[harness] FAIL evaluation-gate: " + "; ".join(failures))
        return {"name": "evaluation-gate", "status": "FAIL", "failures": failures, "result": result}
    print("[harness] PASS evaluation-gate")
    return {"name": "evaluation-gate", "status": "PASS", "result": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ChainJian AML verification harness")
    parser.add_argument("suite", choices=("unit", "compile", "frontend", "smoke", "eval", "all"))
    parser.add_argument("--skip-eval", action="store_true", help="skip local SQLite evaluation gate")
    args = parser.parse_args()

    results: list[dict[str, Any]] = []
    if args.suite in ("unit", "all"):
        results.append(unit())
    if args.suite in ("compile", "all"):
        results.append(compile_python())
    if args.suite in ("frontend", "all"):
        results.append(frontend())
    if args.suite == "smoke":
        results.append(smoke())
    if args.suite in ("eval", "all") and not args.skip_eval:
        results.append(evaluation())
    failed = [item for item in results if item["status"] == "FAIL"]
    print("\n[harness] summary")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
