"""Alert centre page."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR))

from data_access import list_alerts

st.set_page_config(page_title="预警中心 · 链鉴 AML", page_icon="⚠️", layout="wide")
st.title("预警中心")

filters = st.columns(2)
risk_level = filters[0].selectbox("风险等级", ["全部", "HIGH", "MEDIUM", "LOW"])
status = filters[1].selectbox("处理状态", ["全部", "PENDING", "CONFIRMED", "REJECTED"])
alerts = list_alerts(risk_level, status)

if not alerts:
    st.info("当前筛选条件下没有预警。")
else:
    rows = [{
        "alert_id": alert["alert_id"], "account_id": alert["account_id"], "risk_score": alert["risk_score"],
        "risk_level": alert["risk_level"], "rule_hits": ", ".join(alert["rule_hits"]),
        "status": alert["status"], "created_time": alert["created_time"],
    } for alert in alerts]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    selected_id = st.selectbox("选择预警查看详情", [row["alert_id"] for row in rows])
    if st.button("进入预警详情", type="primary"):
        st.session_state["selected_alert_id"] = selected_id
        st.switch_page("pages/alert_detail.py")
