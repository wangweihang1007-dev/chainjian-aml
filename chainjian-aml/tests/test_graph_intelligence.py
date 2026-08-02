import unittest

from graph_intelligence.counterfactual import analyze_counterfactual
from graph_intelligence.risk_propagation import propagate_associated_review


class GraphIntelligenceTest(unittest.TestCase):
    def setUp(self):
        self.subgraph = {
            "edges": [
                {"transaction_id": "T1", "source": "A", "target": "B", "evidence_type": "direct_hit", "priority": 1.0},
                {"transaction_id": "T2", "source": "B", "target": "C", "evidence_type": "direct_hit", "priority": 1.0},
                {"transaction_id": "T3", "source": "C", "target": "A", "evidence_type": "direct_hit", "priority": 1.0},
            ]
        }

    def test_counterfactual_flags_loop_break(self):
        results = analyze_counterfactual(self.subgraph)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(item["after_removal"]["has_closed_loop"] is False for item in results))
        self.assertTrue(all(item["impact_level"] == "HIGH" for item in results))

    def test_propagation_is_bounded_and_attributable(self):
        results = propagate_associated_review(self.subgraph, "A", max_hops=2)
        self.assertEqual({item["account_id"] for item in results}, {"B", "C"})
        self.assertTrue(all(item["classification"] == "associated_review" for item in results))
        self.assertTrue(all(item["hops"] <= 2 for item in results))


if __name__ == "__main__":
    unittest.main()
