"""
Cấu hình tập trung — module AI phát hiện bất thường QoS (báo cáo môn học).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "dev")

DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"
SQL_DIR = PROJECT_ROOT / "sql"

SAMPLE_LOGS_PATH = DATA_RAW_DIR / "train_logs_1000.csv"
SAMPLE_LOGS_JSON_PATH = DATA_RAW_DIR / "train_logs_1000.json"
MODEL_BUNDLE_PATH = MODELS_DIR / "isolation_forest_bundle.joblib"
EVAL_REPORT_PATH = REPORTS_DIR / "evaluation_report.json"
EDA_FIGURES_DIR = REPORTS_DIR / "eda_figures"
MODEL_REGISTRY_PATH = Path(
    os.getenv("MODEL_REGISTRY_PATH", str(MODELS_DIR / "registry.json"))
)

DEFAULT_N_ESTIMATORS = int(os.getenv("N_ESTIMATORS", "300"))
DEFAULT_CONTAMINATION = float(os.getenv("CONTAMINATION", "0.08"))
DEFAULT_MAX_SAMPLES = os.getenv("MAX_SAMPLES", "auto")
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "42"))

RATE_WINDOW_SECONDS = int(os.getenv("RATE_WINDOW_SECONDS", "60"))
TRAIN_RATIO = float(os.getenv("TRAIN_RATIO", "0.7"))
VAL_RATIO = float(os.getenv("VAL_RATIO", "0.15"))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:secret@localhost:5432/qos_anomaly",
)

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

ANOMALY_TYPES = ("normal", "spam", "high_latency", "system_error")

HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "200"))
VIZ_SAMPLE_SIZE = int(os.getenv("VIZ_SAMPLE_SIZE", "5000"))
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


@dataclass(frozen=True)
class Settings:
    app_env: str
    project_root: Path
    models_dir: Path
    model_bundle_path: Path
    model_registry_path: Path
    eval_report_path: Path
    database_url: str
    history_limit: int
    viz_sample_size: int
    random_state: int
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_env=APP_ENV,
            project_root=PROJECT_ROOT,
            models_dir=MODELS_DIR,
            model_bundle_path=MODEL_BUNDLE_PATH,
            model_registry_path=MODEL_REGISTRY_PATH,
            eval_report_path=EVAL_REPORT_PATH,
            database_url=DATABASE_URL,
            history_limit=HISTORY_LIMIT,
            viz_sample_size=VIZ_SAMPLE_SIZE,
            random_state=RANDOM_STATE,
            api_host=API_HOST,
            api_port=API_PORT,
        )

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in ("dev", "development", "local")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


def ensure_directories() -> None:
    for path in (
        DATA_RAW_DIR,
        MODELS_DIR,
        REPORTS_DIR,
        EDA_FIGURES_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
