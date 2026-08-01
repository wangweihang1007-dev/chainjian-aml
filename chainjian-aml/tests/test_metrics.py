import unittest

from evaluation.metrics import binary_metrics


class MetricsTest(unittest.TestCase):
    def test_perfect_prediction(self) -> None:
        result = binary_metrics({"TX1", "TX2"}, {"TX1", "TX2"})
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 1.0)
        self.assertEqual(result["f1"], 1.0)

    def test_empty_prediction_has_zero_scores(self) -> None:
        result = binary_metrics(set(), {"TX1"})
        self.assertEqual(result["precision"], 0.0)
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["f1"], 0.0)
