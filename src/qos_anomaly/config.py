"""Hằng số dùng chung cho pipeline phát hiện bất thường QoS."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "raw"
MODELS_DIR = PROJECT_ROOT / "models"
SAMPLE_LOGS_PATH = DATA_DIR / "train_logs_1000.csv"

MODEL_BUNDLE_PATH = MODELS_DIR / "isolation_forest_bundle.joblib"
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:secret@localhost:5432/qos_anomaly"
)

RANDOM_STATE = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
RATE_WINDOW_SECONDS = 60
DEFAULT_N_ESTIMATORS = 300
DEFAULT_CONTAMINATION = 0.08
DEFAULT_MAX_SAMPLES = "auto"

LOG_COLUMNS = [
    "timestamp",
    "client_ip",
    "endpoint_uri",
    "http_method",
    "response_time_ms",
    "status_code",
    "bytes_sent",
]
LABEL_COLUMNS = ["is_anomaly", "anomaly_type"]
FEATURE_COLUMNS = [
    "response_time_log1p",
    "status_class",
    "is_5xx",
    "is_4xx",
    "request_rate",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "endpoint_freq",
    "method_code",
    "bytes_sent_log1p",
    "ip_error_rate",
    "ip_avg_latency",
]


def ensure_directories() -> None:
    """Tạo thư mục data và model khi chưa tồn tại."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
