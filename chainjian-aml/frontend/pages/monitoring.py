"""Launch monitoring dashboard."""

from pathlib import Path
import sys

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FRONTEND_DIR.parents[0]
sys.path.insert(0, str(FRONTEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from monitoring.service import collect_metrics

st.set_page_config(page_title="AML Monitoring", page_icon="📈", layout="wide")
st.title("AML上线监控")
if st.button("刷新监控指标", type="primary"):
    st.cache_data.clear()
metrics = collect_metrics(include_graph=True)

quality = metrics["data_quality"]
distribution = metrics["distribution"]
review = metrics["review"]
cols = st.columns(4)
cols[0].metric("交易量", f"{quality['transaction_count']:,}")
cols[1].metric("字段缺失率", f"{quality['missing_field_rate']:.2%}")
cols[2].metric("规则命中案件", metrics["rules"]["total_alert_cases"])
cols[3].metric("待审核案件", review["pending_count"])

st.subheader("数据质量与分布")
st.json({"data_quality": quality, "distribution": distribution, "realtime_sync": metrics.get("realtime_sync")})
st.subheader("规则命中量")
st.bar_chart(metrics["rules"]["hit_counts"])
st.subheader("图谱状态")
st.json(metrics.get("graph", {"status": "UNKNOWN"}))
st.caption(f"Snapshot: {metrics['snapshot_at']}")
