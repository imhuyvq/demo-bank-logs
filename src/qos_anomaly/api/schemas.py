"""Pydantic schemas cho FastAPI (bản rút gọn)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LogRecord(BaseModel):
    timestamp: str = Field(..., examples=["2026-01-15T10:30:00"])
    client_ip: str = Field(..., examples=["10.12.3.45"])
    endpoint_uri: str = Field(..., examples=["/api/v1/transfers/napas"])
    http_method: str = Field(default="POST", examples=["POST"])
    response_time_ms: float = Field(..., ge=0, examples=[120.0])
    status_code: int = Field(..., ge=100, le=599, examples=[200])
    bytes_sent: int = Field(default=0, ge=0, examples=[1500])


class PredictRequest(BaseModel):
    record: LogRecord
    threshold: float | None = None
    model_id: str | None = None
    save_to_db: bool = False


class BatchPredictRequest(BaseModel):
    records: list[LogRecord] = Field(..., min_length=1)
    threshold: float | None = None
    model_id: str | None = None
    save_to_db: bool = False


class PredictionItem(BaseModel):
    timestamp: str
    client_ip: str
    endpoint_uri: str
    http_method: str
    response_time_ms: float
    status_code: int
    bytes_sent: int
    anomaly_score: float
    is_anomaly_pred: int
    predicted_anomaly: bool


class PredictResponse(BaseModel):
    model_id: str | None
    threshold: float
    anomaly_count: int
    total: int
    saved_count: int | None = None
    results: list[PredictionItem]


class ModelInfoResponse(BaseModel):
    model_id: str
    path: str
    trained_at: str
    threshold: float
    best_params: dict[str, Any] = Field(default_factory=dict)
    metrics_val: dict[str, Any] = Field(default_factory=dict)
    metrics_test_preview: dict[str, Any] = Field(default_factory=dict)
    feature_columns: list[str] = Field(default_factory=list)
    sklearn_version: str | None = None
    model_type: str = "IsolationForest"
    is_active: bool = False


class HealthResponse(BaseModel):
    status: str
    app_env: str
    model_ready: bool
    active_model_id: str | None
    message: str
