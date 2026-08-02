"""Streamlit view for single-agent and multi-agent AML investigations."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from api_client import request_json

st.set_page_config(page_title="AML Agent 协作调查", page_icon="🔎", layout="wide")
st.title("AML Agent 协作调查")
st.caption("Supervisor Agent 根据规则命中和账户画像动态分配专业 Agent；所有结果来自当前 Alert、DWD、Neo4j 和账户画像查询。")

mode = st.radio("调查模式", ["Multi-Agent 协作", "兼容：单 Agent"], horizontal=True)
question = st.chat_input("例如：分析 AL000001")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        try:
            if mode == "Multi-Agent 协作":
                result = request_json("/agent/multi-investigate", "POST", {"user_input": question})
                tasks = result.get("tasks", [])
                rows = [{"Agent": item["agent_name"], "任务": item["task_type"], "状态": item["status"], "创建时间": item["created_time"], "开始": item["started_time"], "结束": item["finished_time"], "输出摘要": item["output_summary"]} for item in tasks]
                st.subheader("AI 调查流程")
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.subheader("协作结果")
                result_data = result.get("results", {})
                cols = st.columns(max(1, len(tasks)))
                for col, task in zip(cols, tasks):
                    with col:
                        st.metric(task["agent_name"], task["status"])
                        st.caption(task.get("output_summary") or "等待输出")
                st.subheader("调查报告")
                st.markdown(result.get("report", "暂无报告"))
                st.download_button("下载 Markdown 报告", result.get("report", ""), file_name=f"{result['alert_id']}_multi_agent.md", mime="text/markdown")
            else:
                result = request_json("/agent/investigate", "POST", {"user_input": question})
                trace = result.get("trace", [])
                st.subheader("单 Agent 调查进度")
                st.dataframe(pd.DataFrame(trace), use_container_width=True, hide_index=True)
                st.subheader("调查报告")
                st.markdown(result.get("report", "暂无报告"))
        except Exception as error:
            st.error(str(error))
