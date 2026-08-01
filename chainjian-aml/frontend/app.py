"""ChainJian AML Streamlit review workbench entry point."""

from pathlib import Path
import sys

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(FRONTEND_DIR))

from data_access import dashboard_data

st.set_page_config(page_title="链鉴 AML 审查工作台", page_icon="🔎", layout="wide")
st.markdown("""<style>
    .block-container {max-width: 1450px; padding-top: 2rem;}
    [data-testid="stMetric"] {background: #f7f9fc; border: 1px solid #e5eaf2; border-radius: 10px; padding: 0.75rem;}
    h1, h2, h3 {color: #14365d;}
</style>""", unsafe_allow_html=True)

st.title("链鉴 AML 审查工作台")
st.caption("合规调查辅助系统 · 基于合成数据 · 所有预警须经授权人员复核")

data = dashboard_data()
metrics = st.columns(4)
metrics[0].metric("总账户数", f"{data['total_accounts']:,}")
metrics[1].metric("总交易数", f"{data['total_transactions']:,}")
metrics[2].metric("当前预警", f"{data['alert_count']:,}")
metrics[3].metric("高风险账户", f"{data['high_risk_accounts']:,}")

st.subheader("工作台导航")
st.info("使用左侧导航进入仪表盘、预警中心、预警详情和 Agent 调查页面。系统不会自动冻结账户、拦截交易或提交监管报告。")
