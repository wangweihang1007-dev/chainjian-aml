"""Detailed AML alert review page with evidence graph intelligence."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(FRONTEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent
from agent.tools import get_transaction_path, get_risk_response
from explainability.evidence_builder import EvidenceBuilder
from explainability.risk_explainer import RiskExplainer
from explainability.score_explainer import ScoreExplainer
from counterfactual.analyzer import CounterfactualAnalyzer
from data_access import alert_detail, graph_intelligence, list_alerts
from risk_profile.profile_service import AccountProfileService


def graph_dot(paths: list[dict]) -> str:
    nodes = {account for path in paths for account in path["account_path"]}
    lines = ["digraph AML {", "rankdir=LR;", "node [shape=box style=rounded color='#1f4e79' fontname='Arial'];"]
    ids = {node: f"n{index}" for index, node in enumerate(sorted(nodes))}
    lines.extend(f'{ids[node]} [label="{node}"];' for node in nodes)
    for path in paths:
        for source, target, transfer in zip(path["account_path"], path["account_path"][1:], path["transfers"]):
            label = f"{transfer['transaction_id']}\\n{transfer['amount_paid']} {transfer['payment_currency']}\\n{transfer['timestamp']}"
            lines.append(f'{ids[source]} -> {ids[target]} [label="{label}" fontsize=9 color="#4e79a7"];')
    return "\n".join([*lines, "}"])


st.set_page_config(page_title="AML Alert Detail", page_icon="🔎", layout="wide")
st.title("AML Alert Detail")
alerts = list_alerts()
if not alerts:
    st.info("No alerts available. Run the Rule Engine first.")
    st.stop()

alert_ids = [item["alert_id"] for item in alerts]
default_id = st.session_state.get("selected_alert_id", alert_ids[0])
selected_id = st.selectbox("Alert ID", alert_ids, index=alert_ids.index(default_id) if default_id in alert_ids else 0)
st.session_state["selected_alert_id"] = selected_id
alert = alert_detail(selected_id)
assert alert is not None
try:
    profile = AccountProfileService().get(alert["account_id"])
except Exception as error:
    profile = {"error": str(error), "risk_features": []}

left, centre, right = st.columns([1, 1.5, 1.2])
with left:
    st.subheader("Case")
    st.write(f"**Account:** {alert['account_id']}")
    st.metric("Risk score", alert["risk_score"])
    st.metric("Risk level", alert["risk_level"])
    st.write(f"**Rules:** {', '.join(alert['rule_hits'])}")
    st.write(f"**Status:** {alert['status']}")
    st.subheader("Account risk profile")
    if "error" not in profile:
        st.metric("Transactions", profile["txn_count"])
        st.metric("Total amount", f"{profile['total_amount']:,.2f}")
        st.metric("Counterparties", profile["counterparty_count"])
        st.write(f"**Average holding:** {profile['average_holding_time_minutes'] or 'N/A'} min")
        st.write(f"**Risk features:** {', '.join(profile['risk_features']) or 'None'}")
    else:
        st.warning(f"Profile unavailable: {profile['error']}")
with centre:
    st.subheader("Neo4j transaction paths")
    try:
        paths = get_transaction_path(alert["account_id"])
        if paths:
            st.graphviz_chart(graph_dot(paths), use_container_width=True)
            rows = [{"Path": " -> ".join(path["account_path"]), "Transaction": transfer["transaction_id"], "Amount": f"{transfer['amount_paid']} {transfer['payment_currency']}", "Time": transfer["timestamp"]} for path in paths for transfer in path["transfers"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No 1–3 hop outbound path returned.")
    except Exception as error:
        st.warning(f"Neo4j graph unavailable: {error}")
with right:
    st.subheader("Agent investigation")
    prompt = st.text_area("Question", value=f"Analyze {selected_id}", height=90)
    if st.button("Generate investigation report", type="primary"):
        try:
            result = InvestigationAgent().run(prompt)
            st.success("Investigation completed")
            st.markdown(result["report"])
            st.download_button("Download Markdown report", result["report"], file_name=f"{selected_id}_investigation.md", mime="text/markdown")
        except Exception as error:
            st.error(f"Investigation failed: {error}")
    try:
        response = get_risk_response(selected_id)
        st.markdown("**Advisory response (no automatic account action)**")
        for recommendation in response["recommendations"]:
            st.write(f"- {recommendation}")
    except Exception as error:
        st.caption(f"Risk response unavailable: {error}")

st.divider()
st.subheader("Explainable risk analysis")
try:
    evidence_chain = EvidenceBuilder().build(selected_id)
    explanation = RiskExplainer().explain(evidence_chain)
    score_explanation = ScoreExplainer().explain(evidence_chain)
    explain_left, explain_right = st.columns([1.4, 1])
    with explain_left:
        st.markdown(f"**Why this risk:** {explanation['conclusion']}")
        st.caption(f"Evidence confidence: {explanation['confidence']}")
        for item in evidence_chain.get("evidence", []):
            with st.expander(f"{item['type']} · {item.get('description', '')}", expanded=True):
                if item.get("path"):
                    st.write(f"Path: {item['path']}")
                if item.get("holding_time") is not None:
                    st.write(f"Holding time: {item['holding_time']} minutes")
                transaction_rows = item.get("transactions", [])
                if transaction_rows:
                    st.dataframe(pd.DataFrame(transaction_rows), use_container_width=True, hide_index=True)
                if item.get("paths"):
                    st.write("Neo4j paths:")
                    for path in item["paths"][:5]:
                        st.write(" → ".join(path.get("account_path", [])))
    with explain_right:
        st.metric("Explained total score", score_explanation["total_score"])
        score_rows = [{"Factor": item["factor"], "Score": item["score"], "Raw": item.get("raw_score"), "Reason": item["reason"]} for item in score_explanation.get("score_breakdown", [])]
        st.dataframe(pd.DataFrame(score_rows), use_container_width=True, hide_index=True)
        st.caption(score_explanation.get("method", ""))
except Exception as error:
    st.warning(f"Explainability unavailable: {error}")

st.subheader("Counterfactual risk simulation")
try:
    counterfactual = CounterfactualAnalyzer().analyze(selected_id)
    st.metric("Current risk", counterfactual["current_score"])
    cf_rows = [{"Removed factor": item["removed_factor"], "After removal": item["score_after_removal"], "Impact": item["impact"], "Explanation": item["explanation"], "Simulated": item["simulated"]} for item in counterfactual.get("counterfactuals", [])]
    if cf_rows:
        st.dataframe(pd.DataFrame(cf_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No evidence factor is available for simulation.")
except Exception as error:
    st.warning(f"Counterfactual analysis unavailable: {error}")

st.divider()
st.subheader("Evidence-based graph intelligence")
try:
    intelligence = graph_intelligence(selected_id, max_hops=3)
    subgraph = intelligence["evidence_subgraph"]
    st.caption(f"{len(subgraph.get('edges', []))} bounded edges · direct evidence is separated from associated context")
    role_rows = [{"Account": item["account_id"], "Roles": ", ".join(item["roles"]), "Incoming": item["in_count"], "Outgoing": item["out_count"], "Incoming amount": item["in_amount"], "Outgoing amount": item["out_amount"]} for item in intelligence.get("roles", [])]
    timeline_rows = [{"Step": item["step"], "Transaction": item["transaction_id"], "From": item["from_account"], "To": item["to_account"], "Amount": item["amount"], "Time": item["timestamp"], "Evidence": item["evidence_type"]} for item in intelligence.get("timeline", [])]
    counterfactual_rows = [{"Transaction": item["transaction_id"], "Impact": item["impact_level"], "Score": item["impact_score"], "Explanation": item["explanation"]} for item in intelligence.get("counterfactual", [])]
    associated_rows = [{"Account": item["account_id"], "Classification": item["classification"], "Hops": item["hops"], "Strength": item["path_strength"], "Transactions": " -> ".join(item["path_transaction_ids"])} for item in intelligence.get("associated_review", [])]
    tabs = st.tabs(["Roles", "Timeline", "Counterfactual", "Associated review"])
    with tabs[0]:
        st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)
    with tabs[1]:
        st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)
    with tabs[2]:
        st.dataframe(pd.DataFrame(counterfactual_rows), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.caption("Associated accounts are review leads, not direct risk determinations.")
        st.dataframe(pd.DataFrame(associated_rows), use_container_width=True, hide_index=True)
except Exception as error:
    st.warning(f"Graph intelligence unavailable: {error}")
