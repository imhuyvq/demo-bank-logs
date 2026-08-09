"""Feature engineering cho log QoS."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from qos_anomaly.config import FEATURE_COLUMNS, RATE_WINDOW_SECONDS


METHOD_CODES = {"GET": 0, "POST": 1, "PUT": 2, "DELETE": 3, "PATCH": 4, "HEAD": 5, "OPTIONS": 6}


@dataclass
class FeatureBuilder:
    """Xây dựng đặc trưng; fit trên train để tránh leakage."""

    rate_window_seconds: int = RATE_WINDOW_SECONDS
    endpoint_freq_map_: dict[str, float] = field(default_factory=dict)
    ip_error_rate_map_: dict[str, float] = field(default_factory=dict)
    ip_avg_latency_map_: dict[str, float] = field(default_factory=dict)
    global_median_latency_: float = 0.0
    fitted_: bool = False

    def _compute_request_rate(self, df: pd.DataFrame) -> pd.Series:
        """Tần suất request theo IP trong cửa sổ thời gian."""
        rates = pd.Series(0.0, index=df.index, dtype=float)
        window = pd.Timedelta(seconds=self.rate_window_seconds)
        for _, group in df.groupby("client_ip", sort=False):
            ts = group["timestamp"].sort_values()
            for idx in ts.index:
                t = ts.loc[idx]
                start = t - window
                rates.loc[idx] = float(((ts >= start) & (ts <= t)).sum())
        return rates

    def _time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        hour = df["timestamp"].dt.hour + df["timestamp"].dt.minute / 60.0
        dow = df["timestamp"].dt.dayofweek.astype(float)
        return pd.DataFrame(
            {
                "hour_sin": np.sin(2 * np.pi * hour / 24),
                "hour_cos": np.cos(2 * np.pi * hour / 24),
                "dow_sin": np.sin(2 * np.pi * dow / 7),
                "dow_cos": np.cos(2 * np.pi * dow / 7),
            },
            index=df.index,
        )

    def fit(self, df: pd.DataFrame) -> FeatureBuilder:
        """Học thống kê từ tập train."""
        work = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(work["timestamp"]):
            work["timestamp"] = pd.to_datetime(work["timestamp"], format="ISO8601", errors="coerce")

        endpoint_counts = work["endpoint_uri"].value_counts(normalize=True)
        self.endpoint_freq_map_ = endpoint_counts.to_dict()

        work["is_error"] = (work["status_code"] >= 400).astype(int)
        ip_stats = work.groupby("client_ip").agg(
            error_rate=("is_error", "mean"),
            avg_latency=("response_time_ms", "mean"),
        )
        self.ip_error_rate_map_ = ip_stats["error_rate"].to_dict()
        self.ip_avg_latency_map_ = ip_stats["avg_latency"].to_dict()
        self.global_median_latency_ = float(work["response_time_ms"].median())
        self.fitted_ = True
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Biến đổi log thành ma trận đặc trưng."""
        if not self.fitted_:
            raise RuntimeError("FeatureBuilder chưa fit. Gọi fit() trước transform().")

        work = df.copy()
        if not pd.api.types.is_datetime64_any_dtype(work["timestamp"]):
            work["timestamp"] = pd.to_datetime(work["timestamp"], format="ISO8601", errors="coerce")

        features = pd.DataFrame(index=work.index)
        features["response_time_log1p"] = np.log1p(work["response_time_ms"].clip(lower=0))
        features["status_class"] = (work["status_code"] // 100).astype(float)
        features["is_5xx"] = (work["status_code"] >= 500).astype(float)
        features["is_4xx"] = ((work["status_code"] >= 400) & (work["status_code"] < 500)).astype(float)
        features["request_rate"] = self._compute_request_rate(work)
        features = features.join(self._time_features(work))
        features["endpoint_freq"] = work["endpoint_uri"].map(self.endpoint_freq_map_).fillna(0.0)
        features["method_code"] = work["http_method"].map(METHOD_CODES).fillna(-1).astype(float)
        features["bytes_sent_log1p"] = np.log1p(work["bytes_sent"].clip(lower=0))
        features["ip_error_rate"] = work["client_ip"].map(self.ip_error_rate_map_).fillna(0.0)
        features["ip_avg_latency"] = (
            work["client_ip"].map(self.ip_avg_latency_map_).fillna(self.global_median_latency_)
        )

        for col in FEATURE_COLUMNS:
            if col not in features.columns:
                raise ValueError(f"Thiếu feature: {col}")

        features = features[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
        features = features.fillna(features.median(numeric_only=True))
        return features.astype(float)

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.fit(df).transform(df)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rate_window_seconds": self.rate_window_seconds,
            "endpoint_freq_map": self.endpoint_freq_map_,
            "ip_error_rate_map": self.ip_error_rate_map_,
            "ip_avg_latency_map": self.ip_avg_latency_map_,
            "global_median_latency": self.global_median_latency_,
            "fitted": self.fitted_,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeatureBuilder:
        fb = cls(rate_window_seconds=data.get("rate_window_seconds", RATE_WINDOW_SECONDS))
        fb.endpoint_freq_map_ = data.get("endpoint_freq_map", {})
        fb.ip_error_rate_map_ = data.get("ip_error_rate_map", {})
        fb.ip_avg_latency_map_ = data.get("ip_avg_latency_map", {})
        fb.global_median_latency_ = data.get("global_median_latency", 0.0)
        fb.fitted_ = data.get("fitted", False)
        return fb
