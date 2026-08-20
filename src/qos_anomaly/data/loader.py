"""Đọc và validate dữ liệu log từ CSV/JSON."""
from __future__ import annotations


from pathlib import Path

import pandas as pd

from qos_anomaly.config import LABEL_COLUMNS, LOG_COLUMNS

COLUMN_ALIASES = {
    "response_time": "response_time_ms",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=COLUMN_ALIASES)
    return df


def validate_log_schema(df: pd.DataFrame, require_labels: bool = False) -> None:
    """Kiểm tra schema bắt buộc; raise ValueError nếu thiếu/sai."""
    missing = [c for c in LOG_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc: {missing}")

    if require_labels:
        missing_labels = [c for c in LABEL_COLUMNS if c not in df.columns]
        if missing_labels:
            raise ValueError(f"Thiếu cột nhãn: {missing_labels}")


def clean_logs(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch dữ liệu log: parse timestamp, ép kiểu, loại bản ghi lỗi."""
    out = df.copy()
    out = _normalize_columns(out)
    validate_log_schema(out)

    out["timestamp"] = pd.to_datetime(out["timestamp"], format="ISO8601", errors="coerce")
    out["response_time_ms"] = pd.to_numeric(out["response_time_ms"], errors="coerce")
    out["status_code"] = pd.to_numeric(out["status_code"], errors="coerce")
    out["bytes_sent"] = pd.to_numeric(out["bytes_sent"], errors="coerce")

    out = out.dropna(subset=["timestamp", "response_time_ms", "status_code", "bytes_sent"])
    out["status_code"] = out["status_code"].astype(int)
    out["bytes_sent"] = out["bytes_sent"].astype(int)
    out["response_time_ms"] = out["response_time_ms"].clip(lower=0)

    valid_status = (out["status_code"] >= 100) & (out["status_code"] < 600)
    out = out.loc[valid_status].copy()

    out["client_ip"] = out["client_ip"].astype(str).str.strip()
    out["endpoint_uri"] = out["endpoint_uri"].astype(str).str.strip()
    out["http_method"] = out["http_method"].astype(str).str.upper().str.strip()

    if "is_anomaly" in out.columns:
        out["is_anomaly"] = pd.to_numeric(out["is_anomaly"], errors="coerce").fillna(0).astype(int)
    if "anomaly_type" in out.columns:
        out["anomaly_type"] = out["anomaly_type"].fillna("normal").astype(str)

    return out.sort_values("timestamp").reset_index(drop=True)


def load_logs(path: str | Path, require_labels: bool = False) -> pd.DataFrame:
    """Đọc CSV và trả DataFrame đã làm sạch."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    if path.suffix.lower() != ".csv":
        raise ValueError("Chỉ hỗ trợ file CSV")

    df = pd.read_csv(path)
    if require_labels:
        validate_log_schema(_normalize_columns(df.copy()), require_labels=True)
    return clean_logs(df)
