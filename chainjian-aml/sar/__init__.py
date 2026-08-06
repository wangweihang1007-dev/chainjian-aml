"""Review-only SAR draft pipeline; it never submits a regulatory report."""

from .orchestrator import build_sar_draft

__all__ = ["build_sar_draft"]
