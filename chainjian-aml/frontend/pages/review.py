"""Human review workflow page."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent
from app.review_service import ReviewService
from core.warehouse import DEFAULT_DATABASE

st.set_page_config(page_title="人工审核 · 链鉴 AML", page_icon="✅", layout="wide")
st.title("人工审核")
service = ReviewService(DEFAULT_DATABASE)
pending = service.pending_alerts()

if not pending:
    st.success("当前没有待审核预警。")
    st.stop()

rows = [{"预警编号": item.alert_id, "风险账户": item.account_id, "评分": item.risk_score, "等级": item.risk_level, "规则": ", ".join(item.rule_hits)} for item in pending]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
alert_id = st.selectbox("选择待审核预警", [item.alert_id for item in pending])
selected = next(item for item in pending if item.alert_id == alert_id)

left, right = st.columns([1, 1.5])
with left:
    st.subheader("审核操作")
    reviewer = st.text_input("审核人", placeholder="例如：compliance.reviewer")
    action = st.radio("审核决定", ["CONFIRM", "REJECT", "NEED_MORE_INFO"], format_func=lambda item: {"CONFIRM": "确认风险", "REJECT": "驳回预警", "NEED_MORE_INFO": "需补充调查"}[item])
    comment = st.text_area("审核备注")
    if st.button("提交审核", type="primary"):
        try:
            service.submit_review(alert_id, reviewer, action, comment)
            st.success("审核记录和审计日志已保存。")
            st.rerun()
        except ValueError as error:
            st.error(str(error))
with right:
    st.subheader("Agent 调查报告")
    if st.button("加载案件报告"):
        try:
            st.markdown(InvestigationAgent().investigate(alert_id)["report"])
        except Exception as error:
            st.warning(f"无法生成报告：{error}")
    st.subheader("审核历史")
    history = service.review_history(alert_id)
    if history["reviews"]:
        st.dataframe(pd.DataFrame(history["reviews"]), use_container_width=True, hide_index=True)
    else:
        st.caption("暂无审核记录。")
