"""Offline-only AML rule evaluation. Labels never enter the Rule Engine."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.database import sqlite3
from core.warehouse import DEFAULT_DATABASE
from evaluation.metrics import binary_metrics
from rules.rule_engine import RuleEngine


RULE_EVALUATION_TARGETS = {
    "cycle": ("CYCLE_TRANSFER", "CYCLE"),
    "fan_in": ("FAN_IN_COLLECTION", "FAN-IN"),
    # Split transfers to several recipients are evaluated against the
    # available FAN-OUT ground-truth pattern in this demo dataset.
    "fan_out": ("STRUCTURING_TRANSFER", "FAN-OUT"),
}


def evaluate_rules(warehouse_path: Path = DEFAULT_DATABASE, quality_mode: str | None = None) -> dict:
    """Run predictions first, then compare only in this separate evaluation path."""
    predictions: dict[str, set[str]] = defaultdict(set)
    evaluation_warning = None
    try:
        alerts = RuleEngine(warehouse_path, quality_mode=quality_mode).run()
    except (RuntimeError, OSError, ConnectionError) as exc:
        # A missing graph is an evaluation limitation, not a reason to stop
        # the monitoring cycle. Keep the result explicit for human review.
        alerts = []
        evaluation_warning = f"rule evaluation unavailable: {exc}"
    for alert in alerts:
        for hit in alert.rule_hits:
            for evidence in alert.evidence:
                predictions[hit.rule_code].update(evidence.transaction_ids)

    with sqlite3.connect(warehouse_path) as connection:
        labelled_rows = connection.execute(
            "SELECT transaction_id, pattern_type FROM ods_evaluation_labels_raw WHERE is_laundering = '1'"
        ).fetchall()
    actual_by_pattern: dict[str, set[str]] = defaultdict(set)
    for transaction_id, pattern_type in labelled_rows:
        actual_by_pattern[pattern_type].add(transaction_id)

    predicted_all = set().union(*predictions.values()) if predictions else set()
    actual_all = set().union(*actual_by_pattern.values()) if actual_by_pattern else set()
    rules = {}
    for display_name, (rule_code, label_pattern) in RULE_EVALUATION_TARGETS.items():
        rules[display_name] = binary_metrics(predictions.get(rule_code, set()), actual_by_pattern.get(label_pattern, set()))
    result = {"overall": binary_metrics(predicted_all, actual_all), "rules": rules, "quality_mode": quality_mode or "balanced"}
    if evaluation_warning:
        result["warning"] = evaluation_warning
    return result
