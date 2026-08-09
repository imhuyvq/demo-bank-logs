"""Khởi tạo session state dùng chung giữa các trang."""
from __future__ import annotations

import streamlit as st

THRESHOLD_SLIDER_KEY = "threshold_slider"


def init_session_state() -> None:
    defaults = {
        "input_df": None,
        "raw_row_count": 0,
        "quality_report": None,
        "last_result": None,
        "save_to_db": False,
        "loaded_source": None,  # tránh parse lại mỗi rerun
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def ensure_threshold_slider(default_thr: float) -> float:
    """Đồng bộ slider ngưỡng; trả về giá trị đang dùng."""
    if THRESHOLD_SLIDER_KEY not in st.session_state:
        st.session_state[THRESHOLD_SLIDER_KEY] = float(default_thr)
    return float(st.session_state[THRESHOLD_SLIDER_KEY])


def reset_threshold_to_default(default_thr: float) -> None:
    """Callback on_click — gán trực tiếp vào key widget (mượt, không lệch state)."""
    st.session_state[THRESHOLD_SLIDER_KEY] = float(default_thr)


def clear_detection_input() -> None:
    st.session_state.input_df = None
    st.session_state.raw_row_count = 0
    st.session_state.quality_report = None
    st.session_state.last_result = None
    st.session_state.loaded_source = None
