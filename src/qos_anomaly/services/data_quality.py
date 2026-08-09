"""Đánh giá chất lượng dữ liệu log trước khi chạy phát hiện."""
from __future__ import annotations

from typing import Any

import pandas as pd

from qos_anomaly.config import LOG_COLUMNS


def assess_data_quality(
    cleaned_df: pd.DataFrame,
    raw_row_count: int,
    *,
    required_columns: tuple[str, ...] = tuple(LOG_COLUMNS),
) -> dict[str, Any]:
    """Trả báo cáo chất lượng sau bước làm sạch."""
    cleaned = len(cleaned_df)
    dropped = max(raw_row_count - cleaned, 0)
    drop_rate = (dropped / raw_row_count * 100) if raw_row_count else 0.0

    missing_cols = [c for c in required_columns if c not in cleaned_df.columns]
    status_issues = 0
    latency_issues = 0
    if not cleaned_df.empty:
        status_issues = int(((cleaned_df["status_code"] < 100) | (cleaned_df["status_code"] >= 600)).sum())
        latency_issues = int((cleaned_df["response_time_ms"] < 0).sum())

    time_span = None
    if cleaned > 0 and "timestamp" in cleaned_df.columns:
        ts = pd.to_datetime(cleaned_df["timestamp"])
        time_span = {
            "from": ts.min().isoformat(),
            "to": ts.max().isoformat(),
        }

    unique_ips = int(cleaned_df["client_ip"].nunique()) if cleaned else 0
    unique_endpoints = int(cleaned_df["endpoint_uri"].nunique()) if cleaned else 0

    ready = cleaned > 0 and not missing_cols
    issues: list[str] = []
    if missing_cols:
        issues.append(f"Thiếu cột: {', '.join(missing_cols)}")
    if cleaned == 0:
        issues.append("Không còn bản ghi hợp lệ sau làm sạch")
    if drop_rate > 20:
        issues.append(f"Tỷ lệ loại bỏ cao ({drop_rate:.1f}%)")

    return {
        "ready": ready,
        "raw_row_count": raw_row_count,
        "cleaned_row_count": cleaned,
        "dropped_row_count": dropped,
        "drop_rate_pct": round(drop_rate, 2),
        "missing_columns": missing_cols,
        "invalid_status_count": status_issues,
        "invalid_latency_count": latency_issues,
        "unique_ips": unique_ips,
        "unique_endpoints": unique_endpoints,
        "time_span": time_span,
        "has_labels": "is_anomaly" in cleaned_df.columns,
        "issues": issues,
    }
