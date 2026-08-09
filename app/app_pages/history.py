"""Trang lịch sử phát hiện (PostgreSQL — tùy chọn)."""
from __future__ import annotations

import bootstrap  # noqa: F401

import streamlit as st

from runtime import get_service
from ui import prepare_display_df, result_column_config, section_box

service = get_service()

if not service.check_db():
    st.info("Cần PostgreSQL · `docker compose up -d`")
    st.page_link("app_pages/detect.py", label="Sang Phát hiện", icon=":material/search:")
    st.stop()

with section_box("Lịch sử", icon=":material/history:"):
    if st.button("Làm mới", icon=":material/refresh:", type="tertiary"):
        st.rerun()

    try:
        hist = service.list_history()
        if hist.empty:
            st.caption("Chưa có dữ liệu. Bật lưu DB rồi chạy phát hiện.")
        else:
            view_mode = st.segmented_control(
                "Lọc",
                options=["Tất cả", "Bất thường", "Bình thường"],
                default="Tất cả",
                key="history_result_filter",
            )
            if view_mode is None:
                view_mode = "Tất cả"

            filtered = hist
            if view_mode == "Bất thường":
                filtered = hist[hist["is_anomaly"] == 1]
            elif view_mode == "Bình thường":
                filtered = hist[hist["is_anomaly"] == 0]

            c1, c2 = st.columns(2)
            c1.metric("Tổng", len(hist))
            c2.metric("Bất thường", int(hist["is_anomaly"].sum()))
            show = prepare_display_df(filtered)
            st.caption(f"{len(filtered)} / {len(hist)} dòng")
            st.dataframe(
                show,
                width="stretch",
                height=420,
                hide_index=True,
                column_config=result_column_config(show),
            )
    except Exception as exc:
        st.error(str(exc))
