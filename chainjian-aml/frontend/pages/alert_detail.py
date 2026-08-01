"""Detailed review page for an AML alert case."""

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
from agent.tools import get_transaction_path
from data_access import alert_detail, list_alerts


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


st.set_page_config(page_title="预警详情 · 链鉴 AML", page_icon="🔍", layout="wide")
st.title("预警详情")
all_alerts = list_alerts()
if not all_alerts:
    st.info("暂无预警。请先运行 Rule Engine 或通过预警生成接口创建案件。")
    st.stop()

available_ids = [item["alert_id"] for item in all_alerts]
default_id = st.session_state.get("selected_alert_id", available_ids[0])
selected_id = st.selectbox("预警编号", available_ids, index=available_ids.index(default_id) if default_id in available_ids else 0)
st.session_state["selected_alert_id"] = selected_id
alert = alert_detail(selected_id)
assert alert is not None

left, centre, right = st.columns([1, 1.5, 1.2])
with left:
    st.subheader("账户与风险")
    st.write(f"**账户 ID**：{alert['account_id']}")
    st.metric("风险评分", alert["risk_score"])
    st.metric("风险等级", alert["risk_level"])
    st.write("**命中规则**")
    st.write("、".join(alert["rule_hits"]))
    st.write(f"**状态**：{alert['status']}")
with centre:
    st.subheader("资金图谱（1–3 跳）")
    try:
        paths = get_transaction_path(alert["account_id"])
        if paths:
            st.graphviz_chart(graph_dot(paths), use_container_width=True)
            transfer_rows = [
                {"路径": " → ".join(path["account_path"]), "交易": transfer["transaction_id"], "金额": f"{transfer['amount_paid']} {transfer['payment_currency']}", "时间": transfer["timestamp"]}
                for path in paths for transfer in path["transfers"]
            ]
            st.dataframe(pd.DataFrame(transfer_rows), use_container_width=True, hide_index=True)
        else:
            st.info("未查询到 1–3 跳资金路径。")
    except Exception as error:
        st.warning(f"图谱查询不可用：{error}")
with right:
    st.subheader("Agent 调查")
    prompt = st.text_area("调查问题", value=f"分析 {selected_id}", height=90)
    if st.button("生成调查报告", type="primary"):
        try:
            result = InvestigationAgent().run(prompt)
            st.success("调查完成")
            st.markdown(result["report"])
            st.download_button("下载 Markdown 报告", result["report"], file_name=f"{selected_id}_investigation.md", mime="text/markdown")
        except Exception as error:
            st.error(f"调查失败：{error}")
