import unittest

from counterfactual.risk_simulator import RiskSimulator


class CounterfactualTest(unittest.TestCase):
    def test_simulation_is_read_only_and_reduces_score(self):
        chain = {
            "alert": {"risk_score": 90, "rule_hits": ["CYCLE_TRANSFER"]},
            "evidence": [{"type": "cycle_transaction", "transactions": [{"id": "TX003"}], "path": "A->B->C->A"}],
        }
        score = {"total_score": 90, "score_breakdown": [{"factor": "规则命中", "score": 40, "reason": "CYCLE_TRANSFER"}, {"factor": "图谱风险", "score": 30, "reason": "资金回流路径"}]}
        result = RiskSimulator().simulate(chain, score)
        tx_result = next(item for item in result if item["removed_factor"] == "TX003")
        self.assertEqual(tx_result["score_after_removal"], 20)
        self.assertTrue(tx_result["simulated"])
        self.assertEqual(chain["alert"]["risk_score"], 90)


if __name__ == "__main__":
    unittest.main()
