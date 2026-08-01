"""Command-line entry point for offline AML rule evaluation."""

import json

from evaluation.evaluate_rules import evaluate_rules


if __name__ == "__main__":
    print(json.dumps(evaluate_rules(), ensure_ascii=False, indent=2))
