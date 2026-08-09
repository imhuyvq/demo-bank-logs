"""Tests for detection service."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from qos_anomaly.config import Settings
from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.model.train import train_pipeline
from qos_anomaly.services.data_quality import assess_data_quality
from qos_anomaly.services.detection import DetectionService


@pytest.fixture(scope="module")
def service_bundle(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    model_dir = tmp_path_factory.mktemp("models")
    csv_path = data_dir / "sample.csv"
    model_path = model_dir / "model.joblib"
    df = generate_logs(n_rows=800, anomaly_ratio=0.08, seed=42)
    save_dataset(df, csv_path, data_dir / "sample.json")
    train_pipeline(csv_path, model_path)
    settings = Settings(
        app_env="test",
        project_root=data_dir,
        models_dir=model_dir,
        model_bundle_path=model_path,
        model_registry_path=model_dir / "registry.json",
        eval_report_path=data_dir / "missing_eval.json",
        database_url="postgresql+psycopg2://invalid:5432/test",
        history_limit=50,
        viz_sample_size=1000,
        random_state=42,
        api_host="127.0.0.1",
        api_port=8000,
    )
    return DetectionService(settings=settings), df


def test_assess_data_quality():
    df = pd.DataFrame(
        {
            "timestamp": ["2026-01-01T10:00:00", "2026-01-01T10:01:00"],
            "client_ip": ["10.0.0.1", "10.0.0.2"],
            "endpoint_uri": ["/api/v1/accounts/balance", "/api/v1/transfers/napas"],
            "http_method": ["GET", "POST"],
            "response_time_ms": [100.0, 200.0],
            "status_code": [200, 500],
            "bytes_sent": [1000, 2000],
        }
    )
    report = assess_data_quality(df, raw_row_count=3)
    assert report["cleaned_row_count"] == 2
    assert report["ready"] is True


def test_parse_upload_csv(service_bundle):
    service, df = service_bundle
    csv_bytes = df.head(20).to_csv(index=False).encode("utf-8")
    parsed, raw_count = service.parse_upload("logs.csv", csv_bytes)
    assert raw_count == 20
    assert len(parsed) <= 20


def test_parse_upload_json(service_bundle):
    service, df = service_bundle
    payload = json.dumps(df.head(10).to_dict(orient="records")).encode("utf-8")
    parsed, raw_count = service.parse_upload("logs.json", payload)
    assert raw_count == 10
    assert len(parsed) == 10


def test_detect(service_bundle):
    service, df = service_bundle
    run = service.detect(df.head(30))
    assert len(run.result_df) == 30
    assert "anomaly_score" in run.result_df.columns


def test_model_info(service_bundle):
    service, _ = service_bundle
    info = service.get_model_info()
    assert info["model_type"] == "IsolationForest"
    assert "threshold" in info
