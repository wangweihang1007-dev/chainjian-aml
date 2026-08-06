"""Rule orchestration. APP AlertService owns alert-case persistence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from core.warehouse import DEFAULT_DATABASE
from rules.cycle_rule import CycleRule
from rules.behavior_rule import DailyActivityRule, NearThresholdStructuringRule
from rules.fanin_rule import FanInRule
from rules.advanced_rules import AccountHopRule, AmountPatternRule, CounterpartyBurstRule, CrossBankBurstRule, DormantActivationRule, InOutBalanceRule, NonClosedReturnRule
from rules.layered_flow_rule import LayeredFlowRule
from rules.models import Alert
from rules.multihop_rule import MultiHopRule
from rules.rapid_movement_rule import RapidMovementRule
from rules.structuring_rule import StructuringRule


class RuleEngine:
    """Dispatch AML rules and persist their normalized results atomically."""

    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE, quality_mode: str | None = None) -> None:
        self.warehouse_path = warehouse_path
        # Broad behavioral rules are useful for exploration, but their default
        # thresholds create a large review queue on the demo corpus. Keep them
        # opt-in until they have been calibrated against a representative set.
        include_broad_rules = os.getenv("AML_INCLUDE_BROAD_RULES", "0").lower() in {"1", "true", "yes"}
        include_experimental_rules = os.getenv("AML_INCLUDE_EXPERIMENTAL_RULES", "0").lower() in {"1", "true", "yes"}
        include_layered_rules = os.getenv("AML_INCLUDE_LAYERED_RULES", "0").lower() in {"1", "true", "yes"}
        include_advanced_rules = os.getenv("AML_INCLUDE_ADVANCED_RULES", "0").lower() in {"1", "true", "yes"}
        quality_mode = (quality_mode or os.getenv("AML_QUALITY_MODE", "balanced")).lower()
        self.rules = [
            CycleRule(warehouse_path),
            StructuringRule(warehouse_path),
            NearThresholdStructuringRule(warehouse_path),
            FanInRule(warehouse_path),
            MultiHopRule(warehouse_path),
        ]
        if include_broad_rules:
            self.rules.insert(1, DailyActivityRule(warehouse_path))
        if include_experimental_rules:
            self.rules.append(RapidMovementRule(warehouse_path))
        if include_layered_rules:
            self.rules.append(LayeredFlowRule(warehouse_path, include_gather=True))
        if include_advanced_rules:
            self.rules.extend([
                DormantActivationRule(warehouse_path), AccountHopRule(warehouse_path),
                CounterpartyBurstRule(warehouse_path), AmountPatternRule(warehouse_path),
                InOutBalanceRule(warehouse_path), CrossBankBurstRule(warehouse_path),
                NonClosedReturnRule(warehouse_path),
            ])
        if quality_mode in {"precision80", "high_precision", "high-precision"}:
            # A precision-first profile deliberately keeps only the rule that
            # has passed the current labeled benchmark without false positives.
            self.rules = [CycleRule(warehouse_path)]

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
