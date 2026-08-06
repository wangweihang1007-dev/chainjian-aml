"""Privacy-preserving rendering helpers for review-only SAR drafts."""

from __future__ import annotations

import hashlib


def mask_identifier(value: str) -> str:
    text = str(value or "")
    if len(text) <= 6:
        return "***"
    return f"{text[:3]}***{text[-3:]}"


def stable_subject_id(value: str) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"SUBJ-{digest.upper()}"
