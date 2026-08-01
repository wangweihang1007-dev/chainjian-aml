"""Dependency-free binary classification metrics for AML evaluation."""

from __future__ import annotations


def binary_metrics(predicted: set[str], actual: set[str]) -> dict[str, float | int]:
    true_positive = len(predicted & actual)
    false_positive = len(predicted - actual)
    false_negative = len(actual - predicted)
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "tp": true_positive, "fp": false_positive, "fn": false_negative}
