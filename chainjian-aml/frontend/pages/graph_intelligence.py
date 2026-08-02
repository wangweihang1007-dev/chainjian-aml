"""Evidence-based case graph view."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(FRONTEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from data_access import graph_intelligence, list_alerts

st.set_page_config(page_title="AML Graph Intelligence", page_icon="🕸️", layout="wide")
st.title("Evidence-based graph intelligence")
alerts = list_alerts()
if not alerts:
    st.info("No alerts available. Run the Rule Engine first.")
    st.stop()

alert_ids = [item["alert_id"] for item in alerts]
selected_id = st.selectbox("Alert", alert_ids, index=alert_ids.index(st.session_state.get("selected_alert_id", alert_ids[0])) if st.session_state.get("selected_alert_id", alert_ids[0]) in alert_ids else 0)
st.session_state["selected_alert_id"] = selected_id
try:
    result = graph_intelligence(selected_id, max_hops=3)
    subgraph = result["evidence_subgraph"]
    st.caption(f"Account {result['account_id']} · {result['risk_level']} · score {result['risk_score']:.0f} · rules: {', '.join(result['rule_hits'])}")
    st.metric("Bounded evidence edges", len(subgraph.get("edges", [])))
    role_rows = [{"Account": item["account_id"], "Roles": ", ".join(item["roles"]), "Incoming": item["in_count"], "Outgoing": item["out_count"], "Incoming amount": item["in_amount"], "Outgoing amount": item["out_amount"]} for item in result.get("roles", [])]
    timeline_rows = [{"Step": item["step"], "Transaction": item["transaction_id"], "From": item["from_account"], "To": item["to_account"], "Amount": item["amount"], "Time": item["timestamp"], "Evidence": item["evidence_type"]} for item in result.get("timeline", [])]
    edge_rows = subgraph.get("edges", [])
    counterfactual_rows = [{"Transaction": item["transaction_id"], "Impact": item["impact_level"], "Impact score": item["impact_score"], "Explanation": item["explanation"]} for item in result.get("counterfactual", [])]
    associated_rows = [{"Account": item["account_id"], "Classification": item["classification"], "Hops": item["hops"], "Path strength": item["path_strength"], "Transactions": " -> ".join(item["path_transaction_ids"])} for item in result.get("associated_review", [])]
    tab_roles, tab_timeline, tab_edges, tab_explain = st.tabs(["Account roles", "Timeline replay", "Evidence edges", "Explainability"])
    with tab_roles:
        st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)
    with tab_timeline:
        st.dataframe(pd.DataFrame(timeline_rows), use_container_width=True, hide_index=True)
    with tab_edges:
        st.dataframe(pd.DataFrame(edge_rows), use_container_width=True, hide_index=True)
    with tab_explain:
        st.subheader("Key transaction counterfactuals")
        st.dataframe(pd.DataFrame(counterfactual_rows), use_container_width=True, hide_index=True)
        st.subheader("Associated accounts for manual review")
        st.caption("These are bounded review leads, not direct risk determinations.")
        st.dataframe(pd.DataFrame(associated_rows), use_container_width=True, hide_index=True)
except Exception as error:
    st.error(f"Graph intelligence unavailable: {error}")
