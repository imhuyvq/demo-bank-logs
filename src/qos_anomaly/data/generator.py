"""Sinh dataset log API ngân hàng (mô phỏng gần thực tế) có nhãn đánh giá."""
from __future__ import annotations


from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qos_anomaly.config import (
    LABEL_COLUMNS,
    LOG_COLUMNS,
    RANDOM_STATE,

    SAMPLE_LOGS_PATH,
    ensure_directories,
)

# Endpoint kiểu core banking / digital banking 2024–2026
BANK_ENDPOINTS = [
    "/api/v1/auth/login",
    "/api/v1/auth/otp/verify",
    "/api/v1/accounts/balance",
    "/api/v1/accounts/statements",
    "/api/v1/transfers/internal",
    "/api/v1/transfers/napas",
    "/api/v1/payments/bill",
    "/api/v1/cards/transactions",
    "/api/v1/cards/lock",
    "/api/v1/loans/status",
    "/api/v1/savings/deposit",
    "/api/v1/ibanking/session",
    "/api/v1/notifications/push",
    "/api/v1/qr/pay",
]

HTTP_METHODS = ["GET", "POST", "PUT", "DELETE"]


def _random_ip(rng: np.random.Generator) -> str:
    # IP khách hàng / mobile banking NAT thường gặp
    return f"10.{rng.integers(0, 50)}.{rng.integers(0, 255)}.{rng.integers(1, 254)}"


def _normal_row(rng: np.random.Generator, ts: datetime, client_ip: str) -> dict[str, Any]:
    endpoint = str(rng.choice(BANK_ENDPOINTS))
    # Banking: GET balance/statement nhiều, POST transfer/OTP
    if "auth" in endpoint or "transfers" in endpoint or "payments" in endpoint or "otp" in endpoint:
        method = "POST"
    elif "cards/lock" in endpoint:
        method = str(rng.choice(["POST", "PUT"]))
    else:
        method = str(rng.choice(["GET", "POST"], p=[0.7, 0.3]))

    # Latency core banking thường thấp–trung bình
    latency = float(np.clip(rng.lognormal(mean=4.2, sigma=0.45), 8, 900))
    status = int(rng.choice([200, 201, 204, 400], p=[0.72, 0.1, 0.08, 0.1]))
    bytes_sent = int(rng.integers(180, 6000))
    return {
        "timestamp": ts.isoformat(),
        "client_ip": client_ip,
        "endpoint_uri": endpoint,
        "http_method": method,
        "response_time_ms": round(latency, 2),
        "status_code": status,
        "bytes_sent": bytes_sent,
        "is_anomaly": 0,
        "anomaly_type": "normal",
    }


def _spam_rows(
    rng: np.random.Generator,
    base_ts: datetime,
    client_ip: str,
    n_burst: int,
) -> list[dict[str, Any]]:
    """Brute-force login / OTP — kiểu tấn bảo mật ngân hàng."""
    endpoint = str(rng.choice(["/api/v1/auth/login", "/api/v1/auth/otp/verify"]))
    rows = []
    for i in range(n_burst):
        ts = base_ts + timedelta(milliseconds=int(200 + i * 150))
        rows.append(
            {
                "timestamp": ts.isoformat(),
                "client_ip": client_ip,
                "endpoint_uri": endpoint,
                "http_method": "POST",
                "response_time_ms": round(float(rng.uniform(25, 180)), 2),
                "status_code": int(rng.choice([401, 403, 429, 200], p=[0.45, 0.2, 0.25, 0.1])),
                "bytes_sent": int(rng.integers(80, 600)),
                "is_anomaly": 1,
                "anomaly_type": "spam",
            }
        )
    return rows


def _high_latency_row(rng: np.random.Generator, ts: datetime, client_ip: str) -> dict[str, Any]:
    """Timeout cổng thanh toán / NAPAS / core chậm."""
    endpoint = str(
        rng.choice(
            [
                "/api/v1/transfers/napas",
                "/api/v1/payments/bill",
                "/api/v1/qr/pay",
                "/api/v1/accounts/statements",
            ]
        )
    )
    return {
        "timestamp": ts.isoformat(),
        "client_ip": client_ip,
        "endpoint_uri": endpoint,
        "http_method": "POST" if "accounts" not in endpoint else "GET",
        "response_time_ms": round(float(rng.uniform(3500, 18000)), 2),
        "status_code": int(rng.choice([200, 504, 408], p=[0.25, 0.55, 0.2])),
        "bytes_sent": int(rng.integers(200, 4000)),
        "is_anomaly": 1,
        "anomaly_type": "high_latency",
    }


def _system_error_row(rng: np.random.Generator, ts: datetime, client_ip: str) -> dict[str, Any]:
    """Lỗi core / middleware ngân hàng."""
    return {
        "timestamp": ts.isoformat(),
        "client_ip": client_ip,
        "endpoint_uri": str(rng.choice(BANK_ENDPOINTS)),
        "http_method": str(rng.choice(["GET", "POST"])),
        "response_time_ms": round(float(rng.uniform(400, 6000)), 2),
        "status_code": int(rng.choice([500, 502, 503], p=[0.4, 0.3, 0.3])),
        "bytes_sent": int(rng.integers(50, 1500)),
        "is_anomaly": 1,
        "anomaly_type": "system_error",
    }


def generate_logs(
    n_rows: int = 1000,
    anomaly_ratio: float = 0.08,
    seed: int = RANDOM_STATE,
    start_time: datetime | None = None,
) -> pd.DataFrame:
    """Sinh log API ngân hàng mô phỏng (có nhãn)."""
    rng = np.random.default_rng(seed)
    # Khoảng thời gian gần đây hơn (Q1 2026) — phù hợp báo cáo mới
    start = start_time or datetime(2026, 1, 5, 7, 0, 0)
    n_anomaly = int(n_rows * anomaly_ratio)
    n_normal = n_rows - n_anomaly

    rows: list[dict[str, Any]] = []
    ip_pool = [_random_ip(rng) for _ in range(180)]

    for _ in range(n_normal):
        # Giờ cao điểm banking: sáng / trưa / tối
        day_sec = int(rng.choice([9, 10, 11, 12, 13, 17, 18, 19, 20, 21])) * 3600
        ts = start + timedelta(
            days=int(rng.integers(0, 28)),
            seconds=day_sec + int(rng.integers(0, 3500)),
        )
        rows.append(_normal_row(rng, ts, str(rng.choice(ip_pool))))

    n_spam = int(n_anomaly * 0.35)
    n_latency = int(n_anomaly * 0.35)
    n_error = n_anomaly - n_spam - n_latency

    while n_spam > 0:
        ts = start + timedelta(days=int(rng.integers(0, 28)), seconds=int(rng.integers(0, 86400)))
        burst = min(int(rng.integers(8, 20)), n_spam)
        rows.extend(_spam_rows(rng, ts, _random_ip(rng), burst))
        n_spam -= burst

    for _ in range(n_latency):
        ts = start + timedelta(days=int(rng.integers(0, 28)), seconds=int(rng.integers(0, 86400)))
        rows.append(_high_latency_row(rng, ts, str(rng.choice(ip_pool))))

    for _ in range(n_error):
        ts = start + timedelta(days=int(rng.integers(0, 28)), seconds=int(rng.integers(0, 86400)))
        rows.append(_system_error_row(rng, ts, str(rng.choice(ip_pool))))

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    if len(df) > n_rows:
        df = df.iloc[:n_rows].copy()
    elif len(df) < n_rows:
        extra = n_rows - len(df)
        more = []
        for _ in range(extra):
            ts = start + timedelta(days=int(rng.integers(0, 28)), seconds=int(rng.integers(0, 86400)))
            more.append(_normal_row(rng, ts, str(rng.choice(ip_pool))))
        df = (
            pd.DataFrame(rows + more)
            .sort_values("timestamp")
            .reset_index(drop=True)
            .iloc[:n_rows]
        )

    for col in LOG_COLUMNS + LABEL_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"Missing column after generation: {col}")
    return df[LOG_COLUMNS + LABEL_COLUMNS]


def save_dataset(df: pd.DataFrame, path: Path = SAMPLE_LOGS_PATH) -> Path:
    """Lưu dataset mẫu dưới dạng CSV."""
    ensure_directories()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
