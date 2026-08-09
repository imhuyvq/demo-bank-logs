"""UI helpers — section box, STT, cột hiển thị."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pandas as pd
import streamlit as st

_HIDE_HEADING_LINK_CSS = """
<style>
[data-testid="stHeaderActionElements"] {
  display: none !important;
}
</style>
"""

# Đổi tên cột thân thiện khi hiển thị bảng kết quả
RESULT_COLUMN_LABELS = {
    "STT": "STT",
    "timestamp": "Thời gian",
    "client_ip": "IP",
    "endpoint_uri": "API",
    "http_method": "HTTP",
    "response_time_ms": "Latency (ms)",
    "status_code": "Status",
    "bytes_sent": "Bytes",
    "anomaly_score": "Điểm số",
    "is_anomaly_pred": "Nhãn",
    "is_anomaly": "Nhãn",
}


def ensure_app_styles() -> None:
    if st.session_state.get("_qos_app_styles"):
        return
    st.markdown(_HIDE_HEADING_LINK_CSS, unsafe_allow_html=True)
    st.session_state._qos_app_styles = True


def section_header(
    title: str,
    *,
    icon: str,
    help_text: str | None = None,
    tip_key: str | None = None,
) -> None:
    if not help_text:
        st.markdown(f"**{icon} {title}**")
        return

    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.markdown(f"**{icon} {title}**")
        st.button(
            " ",
            icon=":material/info:",
            help=help_text,
            type="tertiary",
            key=tip_key or f"tip_{title}",
        )


def title_with_tip(
    markdown_title: str,
    help_text: str,
    *,
    tip_key: str,
) -> None:
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        st.markdown(markdown_title)
        st.button(
            " ",
            icon=":material/info:",
            help=help_text,
            type="tertiary",
            key=tip_key,
        )


@contextmanager
def section_box(
    title: str,
    *,
    icon: str,
    help_text: str | None = None,
    tip_key: str | None = None,
) -> Iterator[None]:
    ensure_app_styles()
    with st.container(border=True):
        section_header(title, icon=icon, help_text=help_text, tip_key=tip_key)
        yield


def with_stt(df: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột STT bắt đầu từ 1."""
    if df is None or len(df) == 0:
        return df if df is not None else pd.DataFrame()
    out = df.copy()
    if "STT" in out.columns:
        out = out.drop(columns=["STT"])
    out.insert(0, "STT", range(1, len(out) + 1))
    return out


def prepare_display_df(df: pd.DataFrame) -> pd.DataFrame:
    """STT + nhãn tiếng Việt cho cột kết quả."""
    out = with_stt(df)

    # Tránh trùng tên cột "Nhãn" khi có cả is_anomaly và is_anomaly_pred
    label_src = None
    if "is_anomaly_pred" in out.columns:
        label_src = "is_anomaly_pred"
    elif "is_anomaly" in out.columns:
        label_src = "is_anomaly"

    rename = {
        k: v
        for k, v in RESULT_COLUMN_LABELS.items()
        if k in out.columns and k not in ("is_anomaly", "is_anomaly_pred")
    }
    out = out.rename(columns=rename)

    if label_src is not None:
        mapped = out[label_src].map({1: "Bất thường", 0: "Bình thường"})
        out["Nhãn"] = mapped.fillna(out[label_src].astype(str))
        drop_cols = [c for c in ("is_anomaly_pred", "is_anomaly") if c in out.columns]
        out = out.drop(columns=drop_cols)

    return out


def result_column_config(df: pd.DataFrame) -> dict[str, Any]:
    """column_config cho bảng kết quả đã prepare_display_df."""
    cfg: dict[str, Any] = {
        "STT": st.column_config.NumberColumn("STT", width="small"),
    }
    if "Điểm số" in df.columns:
        cfg["Điểm số"] = st.column_config.NumberColumn("Điểm số", format="%.4f")
    if "Latency (ms)" in df.columns:
        cfg["Latency (ms)"] = st.column_config.NumberColumn("Latency (ms)", format="%.1f")
    if "Nhãn" in df.columns:
        cfg["Nhãn"] = st.column_config.TextColumn("Nhãn", width="medium")
    return cfg


def render_step_bar(*, has_input: bool, has_result: bool) -> None:
    """Thanh tiến trình kiểu wizard (pattern demo ML phổ biến)."""
    s1 = "complete" if has_input or has_result else "active"
    s2 = "complete" if has_result else ("active" if has_input else "pending")
    s3 = "complete" if has_result else "pending"

    def _badge(label: str, state: str) -> str:
        if state == "complete":
            return f":green-badge[{label}]"
        if state == "active":
            return f":orange-badge[{label}]"
        return f":gray-badge[{label}]"

    st.markdown(
        f"{_badge('1 · Dữ liệu', s1)} → "
        f"{_badge('2 · Phân tích', s2)} → "
        f"{_badge('3 · Kết quả', s3)}"
    )


def kpi_row(items: list[tuple[str, str | int | float, str | None]]) -> None:
    """Hàng KPI card (dashboard pattern). items = (label, value, delta|None)."""
    cols = st.container(horizontal=True, gap="small")
    with cols:
        for label, value, delta in items:
            st.metric(label, value, delta=delta, border=True)
