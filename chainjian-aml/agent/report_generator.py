"""Grounded AML investigation report generation."""

from __future__ import annotations

from typing import Any, Callable

from agent.prompt import INVESTIGATION_PROMPT


def generate_report(data: dict[str, Any], llm: Callable[[str, dict[str, Any]], str] | None = None) -> str:
    """Generate from exact tool data; the deterministic path never invents facts."""
    if llm:
        return llm(INVESTIGATION_PROMPT, data)
    return _render_deterministic_report(data)


def _render_deterministic_report(data: dict[str, Any]) -> str:
    alert = data["alert"]
    graph = data.get("graph_intelligence", {})
    profile = data.get("account_profile", {})
    conclusion = data.get("risk_conclusion", {})
    evidence = data.get("transaction_evidence", [])
    paths = data.get("transaction_paths", [])
    rule_hits = ", ".join(alert.get("rule_hits", [])) or "None"
    path_lines = [f"- {' -> '.join(path['account_path'])}" for path in paths] or ["- No outbound path returned by Neo4j."]
    evidence_lines = [f"| {row['transaction_id']} | {row['timestamp']} | {row['from_account_id']} | {row['to_account_id']} | {row['amount_paid']} {row['payment_currency']} |" for row in evidence] or ["| - | - | - | - | - |"]
    role_lines = [f"- {item['account_id']}: {', '.join(item['roles'])}" for item in graph.get("roles", [])] or ["- No graph role evidence available."]
    timeline_lines = [f"- {item['timestamp']}: {item['from_account']} -> {item['to_account']} ({item['amount']} {item['currency']}) [{item['transaction_id']}]" for item in graph.get("timeline", [])[:20]] or ["- No graph timeline available."]
    counterfactual_lines = [f"- {item['transaction_id']}: {item['impact_level']} impact; {item['explanation']}" for item in graph.get("counterfactual", [])[:5]] or ["- No counterfactual result available."]
    associated_lines = [f"- {item['account_id']}: {item['hops']} hop(s), strength {item['path_strength']}, transactions {', '.join(item['path_transaction_ids'])}" for item in graph.get("associated_review", [])[:10]] or ["- No associated review leads available."]
    response = data.get("risk_response", {})
    recommendations = [f"- {item}" for item in response.get("recommendations", [])] or ["- No advisory recommendation available."]
    reasons = [f"- {item}" for item in response.get("reason", [])] or ["- No additional reason returned."]
    profile_lines = [f"- {key}: {value}" for key, value in profile.items() if key in {"txn_count", "total_amount", "inflow_amount", "outflow_amount", "counterparty_count", "average_holding_time_minutes", "anomalous_transaction_count", "risk_features"}] or ["- No account profile returned."]
    return f"""# AML Investigation Report

## Case information

- Alert: {alert['alert_id']}
- Risk account: {alert['account_id']}
- Risk level: {alert['risk_level']}
- Risk score: {alert['risk_score']}
- Status: {alert['status']}
- Rules: {rule_hits}
- Created: {alert['created_time']}

## Neo4j money paths

{chr(10).join(path_lines)}

## DWD transaction evidence

| Transaction | Time | From | To | Amount |
| --- | --- | --- | --- | --- |
{chr(10).join(evidence_lines)}

## Evidence graph account roles

{chr(10).join(role_lines)}

## Account risk profile

{chr(10).join(profile_lines)}

## Evidence timeline

{chr(10).join(timeline_lines)}

## Key transaction counterfactuals

{chr(10).join(counterfactual_lines)}

## Risk conclusion

- Level: {conclusion.get('risk_level', alert.get('risk_level'))}
- Score: {conclusion.get('risk_score', alert.get('risk_score'))}
- Evidence transaction IDs: {', '.join(conclusion.get('evidence_transaction_ids', [])) or 'None returned'}
- Conclusion: {conclusion.get('conclusion', 'Based only on the returned Alert and transaction evidence.')}

## Associated accounts for manual review

{chr(10).join(associated_lines)}

## Advisory risk response

### Reasons

{chr(10).join(reasons)}

### Recommendations

{chr(10).join(recommendations)}

> {response.get('disclaimer', 'Advisory only; no automated account action is executed.')}

## Risk explanation

This report is grounded in the Alert record, Neo4j paths, DWD transactions and the evidence graph returned by tools. It does not make a legal determination.

## Recommended manual checks

1. Verify the business relationship and source of funds for the accounts and transactions listed above.
2. Review the high-impact transactions and associated-account paths first.
3. Record confirm, reject or need-more-info decisions in the review workflow.

## Disclaimer

The report is generated from synthetic/demo data and configured detection rules. It is an investigation aid, not a legal opinion or regulatory filing decision.
"""
