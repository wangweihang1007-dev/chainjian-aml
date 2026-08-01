"""Interactive AML investigation Agent page."""

from pathlib import Path
import sys

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from agent.agent import InvestigationAgent

st.set_page_config(page_title="Agent 调查 · 链鉴 AML", page_icon="🤖", layout="wide")
st.title("AML Investigation Agent")
st.caption("请输入包含预警编号的调查问题，例如：为什么 AL000001 风险高？")

question = st.chat_input("输入调查问题")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("正在查询预警、图谱和交易证据..."):
            try:
                result = InvestigationAgent().run(question)
                st.markdown(result["report"])
                st.caption(f"已引用 {len(result['tool_data']['transaction_evidence'])} 笔交易证据与 {len(result['tool_data']['transaction_paths'])} 条资金路径。")
            except Exception as error:
                st.error(str(error))
