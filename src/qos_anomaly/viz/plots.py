"""Các hàm vẽ biểu đồ (Plotly) — nhãn tiếng Việt."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _label_map(series: pd.Series) -> pd.Series:
    return series.astype(int).map({0: "Bình thường", 1: "Bất thường"})


def score_histogram(df: pd.DataFrame) -> go.Figure:
    pred_col = "is_anomaly_pred" if "is_anomaly_pred" in df.columns else "is_anomaly"
    fig = px.histogram(
        df,
        x="anomaly_score",
        color=_label_map(df[pred_col]),
        nbins=40,
        title="Phân bố điểm bất thường",
        labels={"anomaly_score": "Điểm bất thường", "color": "Dự đoán"},
    )
    return fig


def timeline_scores(df: pd.DataFrame) -> go.Figure:
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"])
    pred_col = "is_anomaly_pred" if "is_anomaly_pred" in work.columns else "is_anomaly"
    fig = px.scatter(
        work,
        x="timestamp",
        y="anomaly_score",
        color=_label_map(work[pred_col]),
        hover_data=["client_ip", "endpoint_uri", "status_code"],
        title="Điểm bất thường theo thời gian",
        labels={
            "timestamp": "Thời gian",
            "anomaly_score": "Điểm bất thường",
            "color": "Dự đoán",
        },
    )
    return fig


def anomaly_breakdown(df: pd.DataFrame) -> go.Figure:
    pred_col = "is_anomaly_pred" if "is_anomaly_pred" in df.columns else "is_anomaly"
    counts = (
        df[pred_col]
        .astype(int)
        .value_counts()
        .rename(index={0: "Bình thường", 1: "Bất thường"})
    )
    fig = px.bar(
        x=counts.index.astype(str),
        y=counts.values,
        labels={"x": "Loại", "y": "Số lượng"},
        title="So sánh bình thường và bất thường",
    )
    return fig
