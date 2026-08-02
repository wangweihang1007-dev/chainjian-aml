"""Rule orchestration. APP AlertService owns alert-case persistence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.warehouse import DEFAULT_DATABASE
from rules.cycle_rule import CycleRule
from rules.behavior_rule import DailyActivityRule, NearThresholdStructuringRule
from rules.fanin_rule import FanInRule
from rules.models import Alert
from rules.multihop_rule import MultiHopRule
from rules.rapid_movement_rule import RapidMovementRule
from rules.structuring_rule import StructuringRule


class RuleEngine:
    """Dispatch AML rules and persist their normalized results atomically."""

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path
        self.rules = [
            CycleRule(warehouse_path),
            StructuringRule(warehouse_path),
            DailyActivityRule(warehouse_path),
            NearThresholdStructuringRule(warehouse_path),
            FanInRule(warehouse_path),
            MultiHopRule(warehouse_path),
            RapidMovementRule(warehouse_path),
        ]

    def run(self) -> list[Alert]:
        return [alert for rule in self.rules for alert in rule.detect()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AML Rule Engine v1.")
    parser.add_argument("--warehouse", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    alerts = RuleEngine(args.warehouse).run()
    from app.alert_service import AlertService
    print(json.dumps([alert.as_dict() for alert in AlertService(args.warehouse).generate(alerts)], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
