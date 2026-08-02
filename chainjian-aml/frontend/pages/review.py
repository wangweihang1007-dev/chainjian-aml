"""Human review page backed entirely by FastAPI."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND_DIR))

from api_client import request_json, review_history, submit_review

st.set_page_config(page_title="人工审核 · 链鉴 AML", page_icon="✅", layout="wide")
st.title("人工审核")

try:
    pending = request_json("/reviews/pending")
except Exception as error:
    st.error(str(error))
    st.stop()
if not pending:
    st.success("当前没有待审核预警。")
    st.stop()

rows = [{"alert_id": item["alert_id"], "account_id": item["account_id"], "risk_score": item["risk_score"], "risk_level": item["risk_level"], "rule_hits": ", ".join(item["rule_hits"])} for item in pending]
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
alert_id = st.selectbox("选择待审核预警", [item["alert_id"] for item in pending])

left, right = st.columns([1, 1.5])
with left:
    st.subheader("审核操作")
    reviewer = st.text_input("审核人", placeholder="例如：compliance.reviewer")
    action = st.radio("审核决定", ["CONFIRM", "REJECT", "NEED_MORE_INFO"], format_func=lambda item: {"CONFIRM": "确认风险", "REJECT": "驳回预警", "NEED_MORE_INFO": "需要补充调查"}[item])
    comment = st.text_area("审核备注")
    if st.button("提交审核", type="primary"):
        try:
            submit_review(alert_id, reviewer, action, comment)
            st.success("审核记录和审计日志已保存。")
            st.rerun()
        except Exception as error:
            st.error(str(error))
with right:
    st.subheader("Agent 调查报告")
    if st.button("加载案件报告"):
        try:
            report = request_json(f"/reports/{alert_id}")
            st.markdown(report["report_markdown"])
        except Exception as error:
            st.warning(f"无法生成报告：{error}")
    st.subheader("审核历史")
    try:
        history = review_history(alert_id)
        if history["reviews"]:
            st.dataframe(pd.DataFrame(history["reviews"]), use_container_width=True, hide_index=True)
        else:
            st.caption("暂无审核记录。")
    except Exception as error:
        st.warning(str(error))
