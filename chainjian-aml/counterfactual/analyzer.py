"""Build evidence and run deterministic counterfactual simulations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.warehouse import DEFAULT_DATABASE
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from counterfactual.risk_simulator import RiskSimulator


class CounterfactualAnalyzer:
    def __init__(self, warehouse_path: Path = DEFAULT_DATABASE) -> None:
        self.warehouse_path = warehouse_path

    def analyze(self, alert_id: str) -> dict[str, Any]:
        chain = EvidenceBuilder(self.warehouse_path).build(alert_id)
        score = ScoreExplainer().explain(chain)
        explanation = RiskExplainer().explain(chain)
        return {"alert_id": alert_id, "current_score": score["total_score"], "evidence_chain": chain, "risk_explanation": explanation, "score_explanation": score, "counterfactuals": RiskSimulator().simulate(chain, score)}
