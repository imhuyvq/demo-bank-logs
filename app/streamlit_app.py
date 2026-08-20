"""Dashboard Streamlit: phát hiện, trực quan, lịch sử SQL, thông tin model."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qos_anomaly.config import FEATURE_COLUMNS, MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.data.loader import clean_logs
from qos_anomaly.db.repository import load_recent_results, save_results
from qos_anomaly.model.predict import load_bundle, predict_dataframe

st.set_page_config(
    page_title="QoS anomaly detection",
    page_icon=":material/security:",
    layout="wide",
)


@st.cache_resource
def get_bundle() -> dict:
    """Tải model một lần, không đọc file model lại sau mỗi widget rerun."""
    return load_bundle(MODEL_BUNDLE_PATH)


@st.cache_data
def load_sample() -> pd.DataFrame:
    """Cache CSV mẫu; người dùng vẫn có thể upload CSV riêng."""
    return pd.read_csv(SAMPLE_LOGS_PATH)


def display_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Chọn các cột dễ đọc cho bảng UI, không thay đổi DataFrame gốc."""
    columns = [
        "timestamp",
        "client_ip",
        "endpoint_uri",
        "http_method",
        "response_time_ms",
        "status_code",
        "bytes_sent",
        "anomaly_score",
        "is_anomaly_pred",
    ]
    labels = {
        "timestamp": "Thời gian",
        "client_ip": "IP",
        "endpoint_uri": "Endpoint",
        "http_method": "Method",
        "response_time_ms": "Latency (ms)",
        "status_code": "HTTP status",
        "bytes_sent": "Bytes",
        "anomaly_score": "Anomaly score",
        "is_anomaly_pred": "Bất thường",
    }
    shown = df[[column for column in columns if column in df.columns]].copy()
    if "is_anomaly_pred" in shown:
        shown["is_anomaly_pred"] = shown["is_anomaly_pred"].map({0: "Không", 1: "Có"})
    return shown.rename(columns=labels)


def set_input(df: pd.DataFrame, source: str) -> None:
    """Lưu batch hợp lệ vào session và xóa kết quả batch trước."""
    st.session_state.input_df = clean_logs(df)
    st.session_state.input_source = source
    st.session_state.result_df = None


def run_detection(bundle: dict, threshold: float, save_to_db: bool) -> None:
    """Predict batch hiện tại, sau đó tùy chọn lưu PostgreSQL."""
    result = predict_dataframe(st.session_state.input_df, bundle, threshold)
    st.session_state.result_df = result
    if save_to_db:
        try:
            st.session_state.db_message = f"Đã lưu {save_results(result)} dòng vào PostgreSQL."
        except Exception as error:
            st.session_state.db_message = f"Không lưu được PostgreSQL: {error}"


for key, value in {"input_df": None, "input_source": None, "result_df": None, "db_message": None}.items():
    st.session_state.setdefault(key, value)

try:
    bundle = get_bundle()
except FileNotFoundError:
    st.error("Chưa có model. Chạy `make train` rồi mở lại app.")
    st.stop()

st.title("Phát hiện bất thường QoS")
st.caption("Isolation Forest trên log HTTP mô phỏng. Model chỉ trả bình thường hoặc bất thường.")

with st.sidebar:
    st.header("Thiết lập phát hiện")
    default_threshold = float(bundle["threshold"])
    threshold = st.number_input("Ngưỡng bất thường", value=default_threshold, format="%.6f")
    save_to_db = st.checkbox("Lưu kết quả vào PostgreSQL")
    st.caption("Score ≥ ngưỡng được gắn nhãn bất thường. Hạ ngưỡng: nhạy hơn, dễ báo nhầm hơn.")
    st.divider()
    st.caption("DB Docker: `make db-up`")

page_detect, page_visualize, page_history, page_info = st.tabs(
    [
        "Phát hiện",
        "Trực quan",
        "Lịch sử SQL",
        "Thông tin model",
    ]
)

with page_detect:
    st.subheader("1. Nguồn dữ liệu")
    source = st.segmented_control("Chọn nguồn", ["Bộ mẫu", "Tải CSV", "Nhập tay"], default="Bộ mẫu")

    if source == "Bộ mẫu":
        sample = load_sample()
        left, right = st.columns([3, 1])
        left.caption(f"`{SAMPLE_LOGS_PATH.name}` · {len(sample):,} dòng log mô phỏng")
        if right.button("Nạp bộ mẫu", type="primary", icon=":material/dataset:"):
            set_input(sample, "Bộ mẫu")
            st.rerun()

    elif source == "Tải CSV":
        upload = st.file_uploader("CSV log HTTP", type="csv")
        if upload is not None:
            try:
                set_input(pd.read_csv(upload), f"Tải lên: {upload.name}")
                st.success(f"Đã nạp `{upload.name}`.")
            except (ValueError, pd.errors.ParserError) as error:
                st.error(str(error))

    else:
        with st.form("manual_log"):
            first, second = st.columns(2)
            timestamp = first.text_input("Thời gian ISO 8601", datetime.now().replace(microsecond=0).isoformat())
            client_ip = first.text_input("Client IP", "10.0.0.1")
            endpoint = second.text_input("Endpoint", "/api/v1/transfers/napas")
            method = second.selectbox("HTTP method", ["GET", "POST", "PUT", "DELETE"])
            latency = first.number_input("Latency (ms)", min_value=0.0, value=100.0)
            status = second.number_input("HTTP status", min_value=100, max_value=599, value=200)
            bytes_sent = first.number_input("Bytes sent", min_value=0, value=1000)
            submitted = st.form_submit_button("Nạp log", type="primary", icon=":material/add:")
        if submitted:
            set_input(
                pd.DataFrame(
                    [{
                        "timestamp": timestamp,
                        "client_ip": client_ip,
                        "endpoint_uri": endpoint,
                        "http_method": method,
                        "response_time_ms": latency,
                        "status_code": status,
                        "bytes_sent": bytes_sent,
                    }]
                ),
                "Nhập tay",
            )
            st.rerun()

    input_df = st.session_state.input_df
    if input_df is None:
        st.info("Chọn một nguồn rồi nạp dữ liệu để chạy phát hiện.")
    else:
        st.subheader("2. Kiểm tra dữ liệu")
        total_source = len(load_sample()) if st.session_state.input_source == "Bộ mẫu" else len(input_df)
        first, second, third, fourth = st.columns(4)
        first.metric("Nguồn", st.session_state.input_source)
        second.metric("Dòng hợp lệ", len(input_df))
        third.metric("Dòng loại bỏ", max(total_source - len(input_df), 0))
        fourth.metric("Số IP", input_df["client_ip"].nunique())
        with st.expander("Xem trước 20 log", expanded=True):
            st.dataframe(display_columns(input_df.head(20)), hide_index=True, height=260)

        st.subheader("3. Chạy phát hiện")
        run, clear = st.columns(2)
        if run.button("Chạy Isolation Forest", type="primary", icon=":material/play_arrow:", width="stretch"):
            with st.spinner("Đang tạo feature và chấm điểm log..."):
                run_detection(bundle, threshold, save_to_db)
            st.rerun()
        if clear.button("Xóa batch hiện tại", icon=":material/delete:", width="stretch"):
            st.session_state.input_df = None
            st.session_state.result_df = None
            st.session_state.db_message = None
            st.rerun()

    result = st.session_state.result_df
    if result is not None:
        st.subheader("4. Kết quả")
        if st.session_state.db_message:
            if st.session_state.db_message.startswith("Đã lưu"):
                st.success(st.session_state.db_message)
            else:
                st.warning(st.session_state.db_message)
        anomaly_count = int(result["is_anomaly_pred"].sum())
        first, second, third = st.columns(3)
        first.metric("Tổng log", len(result))
        second.metric("Bất thường", anomaly_count)
        third.metric("Tỷ lệ bất thường", f"{100 * anomaly_count / len(result):.1f}%")
        filter_mode = st.segmented_control("Lọc kết quả", ["Tất cả", "Chỉ bất thường", "Chỉ bình thường"], default="Tất cả")
        if filter_mode == "Chỉ bất thường":
            shown = result[result["is_anomaly_pred"] == 1]
        elif filter_mode == "Chỉ bình thường":
            shown = result[result["is_anomaly_pred"] == 0]
        else:
            shown = result
        st.caption(f"Hiển thị {len(shown):,}/{len(result):,} dòng")
        st.dataframe(display_columns(shown), hide_index=True, height=420)
        st.download_button(
            "Tải kết quả CSV",
            result.to_csv(index=False).encode("utf-8"),
            "ket_qua_phat_hien.csv",
            "text/csv",
            icon=":material/download:",
        )

with page_visualize:
    st.subheader("Trực quan kết quả lần chạy gần nhất")
    result = st.session_state.result_df
    if result is None:
        st.info("Chạy phát hiện ở tab `Phát hiện` trước.")
    else:
        chart_df = result.copy()
        chart_df["timestamp"] = pd.to_datetime(chart_df["timestamp"])
        chart_df = chart_df.sort_values("timestamp")
        left, right = st.columns(2)
        with left:
            st.markdown("**Anomaly score theo thời gian**")
            st.line_chart(chart_df.set_index("timestamp")["anomaly_score"])
        with right:
            st.markdown("**Số log theo HTTP status**")
            st.bar_chart(chart_df["status_code"].astype(str).value_counts().sort_index())
        left, right = st.columns(2)
        with left:
            st.markdown("**Phân bố latency**")
            st.bar_chart(chart_df["response_time_ms"], height=280)
        with right:
            st.markdown("**Tỷ lệ nhãn dự đoán**")
            counts = chart_df["is_anomaly_pred"].map({0: "Bình thường", 1: "Bất thường"}).value_counts()
            st.bar_chart(counts, height=280)
        st.caption("Biểu đồ dùng native Streamlit. Latency chart hiển thị từng log theo thứ tự thời gian, không phải histogram.")

with page_history:
    st.subheader("Lịch sử đã lưu PostgreSQL")
    limit = st.slider("Số dòng lịch sử", min_value=20, max_value=500, value=100, step=20)
    if st.button("Tải lịch sử từ SQL", icon=":material/refresh:"):
        try:
            st.session_state.history_df = load_recent_results(limit)
        except Exception as error:
            st.session_state.history_error = str(error)
    if st.session_state.get("history_error"):
        st.warning(f"Không đọc được PostgreSQL: {st.session_state.history_error}")
        st.caption("Chạy `make db-up`; lần đầu cần DB volume đúng user/password trong `docker-compose.yml`.")
    history = st.session_state.get("history_df")
    if history is not None:
        if history.empty:
            st.info("Chưa có kết quả nào được lưu.")
        else:
            first, second = st.columns(2)
            first.metric("Dòng lịch sử", len(history))
            second.metric("Bất thường", int(history["is_anomaly"].sum()))
            st.dataframe(history, hide_index=True, height=440)

with page_info:
    st.subheader("Thông tin mô hình")
    first, second, third = st.columns(3)
    first.metric("Thuật toán", "Isolation Forest")
    second.metric("Số feature", len(bundle["feature_columns"]))
    third.metric("Threshold mặc định", f"{bundle['threshold']:.6f}")
    st.markdown("**Tham số train**")
    st.json(bundle["best_params"])
    st.markdown("**Chất lượng trên dataset mô phỏng**")
    quality_left, quality_right = st.columns(2)
    quality_left.metric("F1 validation", f"{bundle['metrics_val']['f1']:.4f}")
    quality_right.metric("F1 test", f"{bundle['metrics_test_preview']['f1']:.4f}")
    st.markdown("**14 feature đầu vào**")
    st.code("\n".join(FEATURE_COLUMNS), language="text")
    st.warning("F1 chỉ đo trên dataset mô phỏng cùng generator. Không dùng để khẳng định hiệu quả production.")
    with st.expander("Nguyên lý ngắn"):
        st.markdown(
            "Isolation Forest tạo nhiều cây split ngẫu nhiên. Log khác biệt thường bị tách khỏi phần lớn log sớm hơn, "
            "nên có path length ngắn và anomaly score cao hơn. Xem `docs/GIAI_THICH_HE_THONG.md` để đọc thuật toán, feature và code trace."
        )
