"""Trang phát hiện bất thường — luồng đơn giản: nạp → chạy → kết quả."""
from __future__ import annotations

import bootstrap  # noqa: F401

from pathlib import Path

import pandas as pd
import streamlit as st

from qos_anomaly.config import SAMPLE_LOGS_PATH
from runtime import get_service
from state import THRESHOLD_SLIDER_KEY, clear_detection_input
from ui import prepare_display_df, result_column_config, section_box

service = get_service()
sample_path = Path(SAMPLE_LOGS_PATH)

quality = st.session_state.quality_report
input_df: pd.DataFrame | None = st.session_state.input_df
has_input = input_df is not None and len(input_df) > 0
has_result = st.session_state.last_result is not None


def _set_input(df: pd.DataFrame, raw_count: int, source_id: str) -> None:
    st.session_state.input_df = df
    st.session_state.raw_row_count = raw_count
    st.session_state.quality_report = service.assess_quality(df, raw_count)
    st.session_state.last_result = None
    st.session_state.loaded_source = source_id


def _run_detect() -> None:
    with st.spinner("Đang phân tích..."):
        try:
            run = service.detect(
                st.session_state.input_df,
                threshold=st.session_state.get(THRESHOLD_SLIDER_KEY),
                save_to_db=st.session_state.save_to_db,
            )
            st.session_state.last_result = run.result_df
            st.session_state._last_run_msg = (
                f"Phát hiện **{run.anomaly_count}** bất thường / {len(run.result_df)} bản ghi"
                + (
                    f" · đã lưu {run.saved_count}"
                    if run.saved_count is not None
                    else ""
                )
            )
            st.rerun()
        except ConnectionError as exc:
            st.warning(str(exc))
        except Exception as exc:
            st.error(str(exc))


# 1) Nguồn dữ liệu
with section_box("1. Nguồn dữ liệu", icon=":material/upload_file:"):
    source = st.segmented_control(
        "Nguồn",
        options=["Bộ mẫu", "Tải tệp", "Nhập tay"],
        default="Bộ mẫu",
        key="detect_source",
        label_visibility="collapsed",
    )
    if source is None:
        source = "Bộ mẫu"

    if source == "Bộ mẫu":
        st.caption(f"`{sample_path.name}` · ~1000 dòng")
        if not sample_path.exists():
            st.error("Thiếu bộ mẫu")
        elif st.button("Nạp bộ mẫu", type="primary", icon=":material/dataset:"):
            try:
                df, raw = service.parse_upload(
                    sample_path.name, sample_path.read_bytes()
                )
                _set_input(df, raw, f"sample:{sample_path.name}")
                st.toast("Đã nạp bộ mẫu", icon=":material/check:")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    elif source == "Tải tệp":
        uploaded = st.file_uploader("CSV hoặc JSON", type=["csv", "json"])
        if uploaded is not None:
            source_id = f"upload:{uploaded.name}:{uploaded.size}"
            if st.session_state.loaded_source != source_id:
                try:
                    df, raw = service.parse_upload(uploaded.name, uploaded.getvalue())
                    _set_input(df, raw, source_id)
                    st.toast(f"Đã tải {uploaded.name}", icon=":material/check:")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    else:
        with st.form("manual_log"):
            c1, c2 = st.columns(2)
            ts = c1.text_input("Thời gian", "2026-01-15T10:30:00")
            ip = c1.text_input("IP khách", "10.12.3.45")
            endpoint = c2.text_input("API", "/api/v1/transfers/napas")
            method = c2.selectbox("HTTP", ["GET", "POST", "PUT", "DELETE"])
            latency = c1.number_input("Latency (ms)", min_value=0.0, value=120.0)
            status = c2.number_input("Status", min_value=100, max_value=599, value=200)
            bytes_sent = c1.number_input("Bytes", min_value=0, value=1500)
            if st.form_submit_button("Thêm bản ghi", type="primary"):
                record = {
                    "timestamp": ts,
                    "client_ip": ip,
                    "endpoint_uri": endpoint,
                    "http_method": method,
                    "response_time_ms": latency,
                    "status_code": int(status),
                    "bytes_sent": int(bytes_sent),
                }
                df, raw = service.parse_manual_record(record)
                _set_input(df, raw, "manual:1")
                st.rerun()

# 2) Chạy phát hiện (khi đã có dữ liệu)
if has_input:
    with section_box("2. Chạy phát hiện", icon=":material/play_arrow:"):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Hợp lệ", len(input_df))
        if quality is not None:
            m2.metric("Dòng thô", quality["raw_row_count"])
            m3.metric("Loại bỏ", quality["dropped_row_count"])
            m4.metric("Số IP", quality["unique_ips"])
            for issue in quality.get("issues") or []:
                st.warning(issue)

        with st.expander("Xem trước 20 dòng"):
            st.dataframe(
                prepare_display_df(input_df.head(20)),
                width="stretch",
                height=220,
                hide_index=True,
            )

        b1, b2 = st.columns([1, 1])
        with b1:
            if st.button(
                "Chạy phát hiện",
                type="primary",
                icon=":material/play_arrow:",
                width="stretch",
            ):
                _run_detect()
        with b2:
            st.button(
                "Xóa dữ liệu",
                icon=":material/delete:",
                width="stretch",
                on_click=clear_detection_input,
            )
else:
    st.info("Chọn nguồn ở bước 1 và nạp dữ liệu để tiếp tục.")

# 3) Kết quả
if has_result:
    with section_box(
        "3. Kết quả",
        icon=":material/analytics:",
        help_text="Lọc Tất cả / Bất thường / Bình thường. STT bắt đầu từ 1.",
        tip_key="tip_detect_result",
    ):
        if st.session_state.get("_last_run_msg"):
            st.success(st.session_state._last_run_msg)

        result = st.session_state.last_result
        n_anom = int(result["is_anomaly_pred"].sum())
        c1, c2, c3 = st.columns(3)
        c1.metric("Tổng", len(result))
        c2.metric("Bất thường", n_anom)
        c3.metric("Tỷ lệ", f"{100 * n_anom / max(len(result), 1):.1f}%")

        view_mode = st.segmented_control(
            "Lọc",
            options=["Tất cả", "Bất thường", "Bình thường"],
            default="Tất cả",
            key="detect_result_filter",
        )
        if view_mode is None:
            view_mode = "Tất cả"

        filtered = result
        if view_mode == "Bất thường":
            filtered = result[result["is_anomaly_pred"] == 1]
        elif view_mode == "Bình thường":
            filtered = result[result["is_anomaly_pred"] == 0]

        show_df = prepare_display_df(filtered)
        st.caption(f"{len(filtered)} / {len(result)} dòng")
        st.dataframe(
            show_df,
            width="stretch",
            height=360,
            hide_index=True,
            column_config=result_column_config(show_df),
        )

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "Tải CSV",
                show_df.to_csv(index=False).encode("utf-8"),
                "ket_qua_phat_hien.csv",
                "text/csv",
                icon=":material/download:",
                width="stretch",
            )
        with d2:
            st.page_link(
                "app_pages/visualize.py",
                label="Xem biểu đồ",
                icon=":material/bar_chart:",
            )
