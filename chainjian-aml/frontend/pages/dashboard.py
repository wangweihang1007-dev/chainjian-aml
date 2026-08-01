"""AML dashboard page."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR))

from data_access import dashboard_data

st.set_page_config(page_title="仪表盘 · 链鉴 AML", page_icon="📊", layout="wide")
st.title("风险仪表盘")
data = dashboard_data()

metrics = st.columns(4)
metrics[0].metric("总账户数", f"{data['total_accounts']:,}")
metrics[1].metric("总交易数", f"{data['total_transactions']:,}")
metrics[2].metric("当前预警", f"{data['alert_count']:,}")
metrics[3].metric("高风险账户", f"{data['high_risk_accounts']:,}")

left, right = st.columns(2)
with left:
    st.subheader("风险等级分布")
    risk_frame = pd.DataFrame(
        [{"风险等级": level, "预警数量": data["risk_distribution"].get(level, 0)} for level in ["HIGH", "MEDIUM", "LOW"]]
    ).set_index("风险等级")
    st.bar_chart(risk_frame)
with right:
    st.subheader("规则命中统计")
    rule_frame = pd.DataFrame(
        [{"规则": rule, "命中次数": count} for rule, count in data["rule_counts"].items()]
    )
    if rule_frame.empty:
        st.info("暂无规则命中数据。")
    else:
        st.bar_chart(rule_frame.set_index("规则"))

st.subheader("账户活跃度 Top 10")
top = pd.DataFrame(data["top_accounts"], columns=["排名", "账户ID", "主体名称", "交易数", "交易总额", "对手方数"])
top["交易总额"] = top["交易总额"].round(2)
st.dataframe(top, use_container_width=True, hide_index=True)
