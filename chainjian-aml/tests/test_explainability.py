import unittest

from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer


class ExplainabilityTest(unittest.TestCase):
    def setUp(self):
        self.chain = {
            "alert": {"risk_level": "HIGH", "risk_score": 90, "rule_hits": ["CYCLE_TRANSFER"]},
            "evidence": [{"type": "cycle_transaction", "path": "A->B->C->A", "transactions": [{"id": "TX1"}]}],
            "transactions": [{"transaction_id": "TX1"}],
            "paths": [],
            "account_profile": {},
        }

    def test_risk_explanation_cites_evidence(self):
        result = RiskExplainer().explain(self.chain)
        self.assertTrue(result["evidence_based"])
        self.assertIn("A->B->C->A", result["reasons"][0]["evidence"])

    def test_score_breakdown_sums_to_alert_score(self):
        result = ScoreExplainer().explain(self.chain)
        self.assertEqual(sum(item["score"] for item in result["score_breakdown"]), result["total_score"])
        self.assertEqual(result["total_score"], 90)


if __name__ == "__main__":
    unittest.main()
