"""Streamlit demo — phát hiện bất thường QoS ngân hàng."""
from __future__ import annotations

import bootstrap  # noqa: F401

import streamlit as st

from runtime import get_service
from state import (
    THRESHOLD_SLIDER_KEY,
    ensure_threshold_slider,
    init_session_state,
    reset_threshold_to_default,
)
from ui import ensure_app_styles, title_with_tip

st.set_page_config(
    page_title="QoS Anomaly · Ngân hàng",
    page_icon=":material/shield:",
    layout="wide",
    initial_sidebar_state="expanded",
)
init_session_state()
ensure_app_styles()

service = get_service()

page = st.navigation(
    [
        st.Page("app_pages/detect.py", title="Phát hiện", icon=":material/search:"),
        st.Page("app_pages/visualize.py", title="Trực quan", icon=":material/bar_chart:"),
        st.Page("app_pages/history.py", title="Lịch sử", icon=":material/history:"),
        st.Page("app_pages/info.py", title="Thông tin", icon=":material/info:"),
    ],
    position="top",
)

ready, message = service.check_model_ready()
if not ready:
    st.error(message, icon=":material/error:")
    st.caption("Chạy `python3 scripts/train_model.py`")
    st.stop()

info = service.get_model_info()
bundle = service.get_bundle()
default_thr = float(bundle["threshold"])
ensure_threshold_slider(default_thr)
db_ok = service.check_db()

with st.sidebar:
    st.markdown("**:material/shield: QoS Anomaly**")
    st.badge(
        info.get("display_name") or "Sẵn sàng",
        icon=":material/check_circle:",
        color="green",
    )
    st.caption(f"`{info.get('model_id', '—')}`")

    if page.title == "Phát hiện":
        st.divider()
        title_with_tip(
            "**Ngưỡng**",
            "Điểm số ≥ ngưỡng → bất thường. Thấp hơn = nhạy hơn.",
            tip_key="tip_threshold",
        )
        span = max(abs(default_thr), 0.05)
        threshold = st.slider(
            "Ngưỡng",
            min_value=round(default_thr - span, 4),
            max_value=round(default_thr + span, 4),
            step=0.001,
            format="%.4f",
            key=THRESHOLD_SLIDER_KEY,
            label_visibility="collapsed",
        )
        if abs(threshold - default_thr) >= 1e-9:
            st.button(
                "Đặt lại",
                icon=":material/restart_alt:",
                type="tertiary",
                width="stretch",
                on_click=reset_threshold_to_default,
                args=(default_thr,),
            )
        else:
            st.caption(f"Mặc định `{default_thr:.4f}`")

        st.toggle("Lưu PostgreSQL", key="save_to_db")
        if st.session_state.save_to_db and not db_ok:
            st.warning("Chưa kết nối DB")

    elif page.title == "Lịch sử":
        st.caption("PostgreSQL" + (" · OK" if db_ok else " · tắt"))

st.markdown(f"**{page.icon} {page.title}**")
page.run()
