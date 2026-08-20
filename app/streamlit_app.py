"""Demo một trang: nạp log, chạy Isolation Forest, xem kết quả."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qos_anomaly.config import MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.data.loader import clean_logs
from qos_anomaly.db.repository import save_results
from qos_anomaly.model.predict import load_bundle, predict_dataframe

st.set_page_config(page_title="QoS anomaly detection", page_icon=":material/security:", layout="wide")
st.title("Phát hiện bất thường QoS")
st.caption("Isolation Forest trên log HTTP mô phỏng. Kết quả là nhị phân: bình thường hoặc bất thường.")


@st.cache_resource
def get_bundle() -> dict:
    """Tải model một lần cho mỗi Streamlit session process."""
    return load_bundle(MODEL_BUNDLE_PATH)


@st.cache_data
def load_sample() -> pd.DataFrame:
    """Nạp dataset mẫu từ project."""
    return pd.read_csv(SAMPLE_LOGS_PATH)


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    """Chỉ giữ cột cần xem khi demo."""
    columns = [
        "timestamp", "client_ip", "endpoint_uri", "http_method", "response_time_ms",
        "status_code", "anomaly_score", "is_anomaly_pred",
    ]
    return df[[column for column in columns if column in df.columns]]


try:
    bundle = get_bundle()
except FileNotFoundError:
    st.error("Chưa có model. Chạy `make train` rồi mở lại app.")
    st.stop()

with st.sidebar:
    st.header("Thiết lập")
    source = st.radio("Nguồn log", ["Bộ mẫu", "Tải CSV"], index=0)
    default_threshold = float(bundle["threshold"])
    threshold = st.number_input("Ngưỡng bất thường", value=default_threshold, format="%.6f")
    save_to_db = st.checkbox("Lưu kết quả vào PostgreSQL")
    st.caption("Điểm số ≥ ngưỡng được gắn nhãn bất thường.")

if source == "Bộ mẫu":
    raw_df = load_sample()
    st.caption(f"Nguồn: `{SAMPLE_LOGS_PATH.name}` · {len(raw_df):,} dòng mô phỏng")
else:
    upload = st.file_uploader("Chọn file CSV", type="csv")
    if upload is None:
        st.info("Tải CSV có 7 cột log bắt buộc để bắt đầu.")
        st.stop()
    raw_df = pd.read_csv(upload)

try:
    input_df = clean_logs(raw_df)
except ValueError as error:
    st.error(str(error))
    st.stop()

st.subheader("1. Dữ liệu đầu vào")
left, right, third = st.columns(3)
left.metric("Dòng gốc", len(raw_df))
right.metric("Dòng hợp lệ", len(input_df))
third.metric("Dòng loại bỏ", len(raw_df) - len(input_df))
st.dataframe(display_table(input_df.head(20)), hide_index=True, height=260)

st.subheader("2. Phát hiện")
if st.button("Chạy Isolation Forest", type="primary", icon=":material/play_arrow:"):
    result = predict_dataframe(input_df, bundle, threshold)
    if save_to_db:
        try:
            st.success(f"Đã lưu {save_results(result)} dòng vào PostgreSQL.")
        except Exception as error:
            st.error(f"Không lưu được PostgreSQL: {error}")
    st.session_state["result"] = result

result = st.session_state.get("result")
if result is not None:
    anomalies = int(result["is_anomaly_pred"].sum())
    st.subheader("3. Kết quả")
    a, b, c = st.columns(3)
    a.metric("Tổng log", len(result))
    b.metric("Bất thường", anomalies)
    c.metric("Tỷ lệ", f"{100 * anomalies / len(result):.1f}%")

    view = st.segmented_control("Hiển thị", ["Tất cả", "Chỉ bất thường"], default="Tất cả")
    shown = result if view == "Tất cả" else result[result["is_anomaly_pred"] == 1]
    st.dataframe(display_table(shown), hide_index=True, height=420)
    st.download_button(
        "Tải kết quả CSV",
        result.to_csv(index=False).encode("utf-8"),
        "ket_qua_phat_hien.csv",
        "text/csv",
        icon=":material/download:",
    )

with st.expander("Ý nghĩa kết quả"):
    st.markdown(
        """
- **Isolation Forest** cô lập các log khác biệt bằng cây ngẫu nhiên; log bị cô lập sớm có điểm bất thường cao.
- Model dùng 14 feature từ latency, HTTP status, tốc độ request, thời gian, endpoint và IP.
- `anomaly_score` càng cao càng bất thường. Model không phân loại spam, latency cao hay system error.
- Dataset là mô phỏng. Xem `docs/GIAI_THICH_HE_THONG.md` trước khi dùng số liệu trong báo cáo.
        """
    )
