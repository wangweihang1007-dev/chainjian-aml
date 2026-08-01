import unittest

from app.risk_score import calculate_risk_score, risk_level


class RiskScoreTest(unittest.TestCase):
    def test_rule_weights_accumulate(self) -> None:
        score = calculate_risk_score(["CYCLE_TRANSFER", "STRUCTURING_TRANSFER", "FAN_IN_COLLECTION"])
        self.assertEqual(score, 95.0)
        self.assertEqual(risk_level(score), "HIGH")

    def test_duplicate_rules_count_once(self) -> None:
        self.assertEqual(calculate_risk_score(["CYCLE_TRANSFER", "CYCLE_TRANSFER"]), 40.0)
