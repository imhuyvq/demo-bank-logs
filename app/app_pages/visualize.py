"""Trang trực quan hóa kết quả."""
from __future__ import annotations

import bootstrap  # noqa: F401

import streamlit as st

from qos_anomaly.config import get_settings
from qos_anomaly.viz.plots import anomaly_breakdown, score_histogram, timeline_scores
from ui import section_box

settings = get_settings()

if st.session_state.last_result is None:
    st.info("Chưa có kết quả. Vào trang Phát hiện để chạy trước.")
    st.page_link("app_pages/detect.py", label="Sang Phát hiện", icon=":material/search:")
    st.stop()

result = st.session_state.last_result.copy()
n_anom = int(result["is_anomaly_pred"].sum())

m1, m2, m3 = st.columns(3)
m1.metric("Tổng", len(result))
m2.metric("Bất thường", n_anom)
m3.metric("Tỷ lệ", f"{100 * n_anom / max(len(result), 1):.1f}%")

with section_box("Bộ lọc", icon=":material/filter_list:"):
    ips = sorted(result["client_ip"].unique().tolist())
    endpoints = sorted(result["endpoint_uri"].unique().tolist())
    f1, f2 = st.columns(2)
    selected_ips = f1.multiselect("IP", options=ips, default=ips, key="viz_ips")
    selected_endpoints = f2.multiselect(
        "API", options=endpoints, default=endpoints, key="viz_endpoints"
    )
    anomaly_filter = st.segmented_control(
        "Loại",
        options=["Tất cả", "Bất thường", "Bình thường"],
        default="Tất cả",
        key="viz_anomaly_filter",
    )

if anomaly_filter is None:
    anomaly_filter = "Tất cả"

filtered = result[
    result["client_ip"].isin(selected_ips)
    & result["endpoint_uri"].isin(selected_endpoints)
]
if anomaly_filter == "Bất thường":
    filtered = filtered[filtered["is_anomaly_pred"] == 1]
elif anomaly_filter == "Bình thường":
    filtered = filtered[filtered["is_anomaly_pred"] == 0]

if filtered.empty:
    st.warning("Không còn dữ liệu sau lọc.")
    st.stop()

viz_df = filtered
if len(viz_df) > settings.viz_sample_size:
    viz_df = viz_df.sample(settings.viz_sample_size, random_state=settings.random_state)

with section_box(
    "Biểu đồ",
    icon=":material/bar_chart:",
    help_text="Điểm số · Thời gian · Nhóm bất thường",
    tip_key="tip_viz_charts",
):
    st.caption(f"{len(filtered)} / {len(result)} bản ghi")
    tab1, tab2, tab3 = st.tabs(["Điểm số", "Thời gian", "Nhóm"])
    with tab1:
        st.plotly_chart(score_histogram(viz_df), width="stretch")
    with tab2:
        st.plotly_chart(timeline_scores(viz_df), width="stretch")
    with tab3:
        st.plotly_chart(anomaly_breakdown(viz_df), width="stretch")
