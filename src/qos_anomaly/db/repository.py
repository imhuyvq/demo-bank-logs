"""Một hàm lưu kết quả; DB không tham gia train hay predict."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, text

from qos_anomaly.config import DATABASE_URL


def save_results(results: pd.DataFrame, url: str = DATABASE_URL) -> int:
    """Lưu từng log và nhãn dự đoán trong một transaction."""
    rows = []
    for row in results.itertuples(index=False):
        rows.append(
            {
                "timestamp": pd.Timestamp(row.timestamp).to_pydatetime(),
                "client_ip": row.client_ip,
                "endpoint_uri": row.endpoint_uri,
                "response_time_ms": float(row.response_time_ms),
                "status_code": int(row.status_code),
                "anomaly_score": float(row.anomaly_score),
                "is_anomaly": bool(row.is_anomaly_pred),
                "predicted_at": datetime.now(timezone.utc),
            }
        )
    statement = text("""
        INSERT INTO detection_results
        (timestamp, client_ip, endpoint_uri, response_time_ms, status_code,
         anomaly_score, is_anomaly, predicted_at)
        VALUES
        (:timestamp, :client_ip, :endpoint_uri, :response_time_ms, :status_code,
         :anomaly_score, :is_anomaly, :predicted_at)
    """)
    with create_engine(url).begin() as connection:
        connection.execute(statement, rows)
    return len(rows)
