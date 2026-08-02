"""Interactive Agent page with auditable investigation progress."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent

st.set_page_config(page_title="AML Investigation Agent", page_icon="🕵️", layout="wide")
st.title("AML Investigation Agent")
st.caption("Agent 会根据预警规则和账户画像动态选择调查工具，所有步骤都会记录到 investigation_trace。")

question = st.chat_input("例如：分析 AL000001")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            result = InvestigationAgent().run(question)
            trace = result.get("trace", [])
            st.subheader("调查进度")
            rows = [{"步骤": item["step_id"], "名称": item["step_name"], "状态": item["status"], "工具": item["tool_name"], "开始": item["started_time"], "结束": item["finished_time"], "结果摘要": item["output_summary"]} for item in trace]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.subheader("调查报告")
            st.markdown(result["report"])
            st.download_button("下载 Markdown 报告", result["report"], file_name=f"{result['alert_id']}_investigation.md", mime="text/markdown")
        except Exception as error:
            st.error(str(error))
