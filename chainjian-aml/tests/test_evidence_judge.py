import unittest

from agents.evidence import build_evidence_index, evidence_item
from agents.evidence_judge import EvidenceJudge


class EvidenceJudgeTest(unittest.TestCase):
    def test_builds_shared_evidence_index(self):
        outputs = {
            "rule_analysis": {"rule_hits": ["RAPID_MOVEMENT"]},
            "transaction_analysis": {"key_transaction_ids": ["TX1", "TX2"]},
        }
        evidence = build_evidence_index(outputs)
        self.assertEqual({item["source"] for item in evidence}, {"Rule Agent", "Transaction Agent"})
        self.assertEqual(evidence[1]["evidence_ids"], ["TX1", "TX2"])

    def test_failed_specialist_requires_more_evidence(self):
        result = EvidenceJudge().evaluate(
            {"risk_level": "HIGH"},
            {"graph_error": "Neo4j unavailable"},
            [evidence_item("Rule Agent", "rule_hit", "命中规则")],
        )
        self.assertEqual(result["status"], "NEEDS_MORE_EVIDENCE")
        self.assertTrue(result["needs_more_evidence"])


if __name__ == "__main__":
    unittest.main()
