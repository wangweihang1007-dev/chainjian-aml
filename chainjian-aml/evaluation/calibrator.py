"""Small dependency-light second-stage calibrator for the offline benchmark."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from math import exp, log
from pathlib import Path

FEATURES = ("source_degree", "target_degree", "source_total", "target_total", "amount", "source_share", "target_share")


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def featurize(rows: list[dict]) -> tuple[list[list[float]], list[int]]:
    out = defaultdict(list); inc = defaultdict(list)
    for row in rows:
        amount = float(row["amount"]); out[row["from_account"]].append(amount); inc[row["to_account"]].append(amount)
    x, y = [], []
    for row in rows:
        amount = float(row["amount"]); source = out[row["from_account"]]; target = inc[row["to_account"]]
        x.append([len(source), len(target), sum(source), sum(target), amount, amount / max(sum(source), 1), amount / max(sum(target), 1)])
        y.append(int(row["is_laundering"]))
    return x, y


def fit(rows: list[dict], epochs: int = 1200, learning_rate: float = 0.05) -> dict:
    x, y = featurize(rows); means = [sum(row[i] for row in x) / max(len(x), 1) for i in range(len(FEATURES))]
    scales = [(sum((row[i] - means[i]) ** 2 for row in x) / max(len(x), 1)) ** 0.5 or 1.0 for i in range(len(FEATURES))]
    z = [[(value - means[i]) / scales[i] for i, value in enumerate(row)] for row in x]
    weights = [0.0] * len(FEATURES); bias = 0.0
    for _ in range(epochs):
        grad = [0.0] * len(FEATURES); bias_grad = 0.0
        for row, label in zip(z, y):
            score = max(-30.0, min(30.0, bias + sum(w * v for w, v in zip(weights, row)))); prob = 1 / (1 + exp(-score)); error = prob - label
            bias_grad += error
            for i, value in enumerate(row): grad[i] += error * value
        count = max(len(z), 1); bias -= learning_rate * bias_grad / count
        weights = [w - learning_rate * g / count for w, g in zip(weights, grad)]
    return {"features": FEATURES, "means": means, "scales": scales, "weights": weights, "bias": bias}


def predict(model: dict, rows: list[dict]) -> list[float]:
    x, _ = featurize(rows); result = []
    for row in x:
        z = [(value - mean) / scale for value, mean, scale in zip(row, model["means"], model["scales"])]
        score = max(-30.0, min(30.0, model["bias"] + sum(w * v for w, v in zip(model["weights"], z))))
        result.append(1 / (1 + exp(-score)))
    return result


def evaluate(model: dict, rows: list[dict], threshold: float = 0.5) -> dict[str, float | int]:
    probabilities = predict(model, rows); actual = [int(row["is_laundering"]) for row in rows]
    predicted = [int(value >= threshold) for value in probabilities]; tp = sum(a == p == 1 for a, p in zip(actual, predicted)); fp = sum(a == 0 and p == 1 for a, p in zip(actual, predicted)); fn = sum(a == 1 and p == 0 for a, p in zip(actual, predicted)); precision = tp / max(tp + fp, 1); recall = tp / max(tp + fn, 1); f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--benchmark-dir", type=Path, default=Path("data/evaluation_benchmark")); parser.add_argument("--model", type=Path, default=Path("data/evaluation_benchmark/calibrator.json")); args = parser.parse_args()
    model = fit(load_rows(args.benchmark_dir / "train.csv")); args.model.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"validation": evaluate(model, load_rows(args.benchmark_dir / "validation.csv")), "test": evaluate(model, load_rows(args.benchmark_dir / "test.csv"))}, ensure_ascii=False, indent=2))
