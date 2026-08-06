"""Search the repository's local AML reference corpus with source citations.

This is a retrieval layer for review drafts, not a current-law oracle. Every
result is labelled as a local reference and requires human verification.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "references" / "aml-rules-md"

RULE_QUERIES = {
    "CYCLE_TRANSFER": "可疑交易 资金回流 循环交易",
    "STRUCTURING_TRANSFER": "拆分交易 分拆 规避监测",
    "FAN_IN_COLLECTION": "多个账户 资金归集 可疑交易",
    "FAN_OUT_DISTRIBUTION": "分散转出 资金流向 可疑交易",
    "RAPID_MOVEMENT": "短时间 快进快出 交易监测",
    "MULTI_HOP_TRANSFER": "多跳 资金链路 可疑交易",
}


def _documents() -> list[Path]:
    return sorted(REFERENCE_ROOT.glob("*.md")) if REFERENCE_ROOT.exists() else []


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _snippet(text: str, terms: list[str], width: int = 260) -> str:
    compact = _compact(text)
    positions = [compact.lower().find(term.lower()) for term in terms if compact.lower().find(term.lower()) >= 0]
    start = max(0, (min(positions) if positions else 0) - 80)
    return compact[start:start + width]


def search_references(query: str, limit: int = 5) -> list[dict[str, Any]]:
    terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]+", query or "") if len(term) > 1]
    if not terms:
        return []
    results: list[dict[str, Any]] = []
    for path in _documents():
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        hits = sum(lowered.count(term.lower()) for term in terms)
        if hits == 0:
            continue
        title = next((line.lstrip("#* ").strip() for line in text.splitlines() if line.strip()), path.stem)
        results.append({
            "reference_id": path.stem,
            "title": title,
            "source_file": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "snippet": _snippet(text, terms),
            "match_count": hits,
            "source_kind": "local_reference",
            "verification_required": True,
            "citation": f"[{title}](docs/references/aml-rules-md/{path.name})",
        })
    return sorted(results, key=lambda item: (-item["match_count"], item["title"]))[: max(1, min(limit, 20))]


def get_legal_basis(rule_hits: list[str], limit_per_rule: int = 2) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in rule_hits or []:
        for item in search_references(RULE_QUERIES.get(rule, rule), limit_per_rule):
            if item["reference_id"] in seen:
                continue
            seen.add(item["reference_id"])
            item = {**item, "linked_rule": rule}
            references.append(item)
    return references
