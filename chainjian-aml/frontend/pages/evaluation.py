"""Offline rule-evaluation page."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from evaluation.evaluate_rules import evaluate_rules
from evaluation.report import metric_rows

st.set_page_config(page_title="检测评估 · 链鉴 AML", page_icon="📈", layout="wide")
st.title("AML 检测效果评估")
st.caption("评估标签仅在此离线评估页面使用，未进入规则引擎、图谱或 Agent 推理。")

if st.button("运行评估", type="primary") or "evaluation_result" not in st.session_state:
    try:
        st.session_state["evaluation_result"] = evaluate_rules()
    except Exception as error:
        st.error(f"评估失败：{error}")
        st.stop()

result = st.session_state["evaluation_result"]
overall = result["overall"]
metrics = st.columns(3)
metrics[0].metric("Precision", f"{overall['precision']:.2%}")
metrics[1].metric("Recall", f"{overall['recall']:.2%}")
metrics[2].metric("F1", f"{overall['f1']:.2%}")

st.subheader("规则级表现")
table = pd.DataFrame(metric_rows(result)).rename(columns={"rule": "规则", "precision": "Precision", "recall": "Recall", "f1": "F1", "tp": "TP", "fp": "FP", "fn": "FN"})
st.dataframe(table, use_container_width=True, hide_index=True)
