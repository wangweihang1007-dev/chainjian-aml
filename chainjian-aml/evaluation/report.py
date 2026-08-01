"""Formatting helper for the evaluation page and API responses."""

from __future__ import annotations


def metric_rows(result: dict) -> list[dict]:
    return [{"rule": name, **metrics} for name, metrics in result["rules"].items()]
