"""Tests for FastAPI predict endpoints."""
from __future__ import annotations

import pytest

from qos_anomaly.config import get_settings
from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.model.train import train_pipeline


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    root = tmp_path_factory.mktemp("api")
    data_dir = root / "data"
    model_dir = root / "models"
    data_dir.mkdir()
    model_dir.mkdir()
    csv_path = data_dir / "sample.csv"
    bundle = model_dir / "isolation_forest_bundle.joblib"
    df = generate_logs(n_rows=800, anomaly_ratio=0.08, seed=99)
    save_dataset(df, csv_path, data_dir / "sample.json")
    train_pipeline(csv_path, bundle)

    import qos_anomaly.config as cfg
    import qos_anomaly.model.registry as reg_mod

    original = {
        "MODELS_DIR": cfg.MODELS_DIR,
        "MODEL_BUNDLE_PATH": cfg.MODEL_BUNDLE_PATH,
        "MODEL_REGISTRY_PATH": cfg.MODEL_REGISTRY_PATH,
        "reg_MODELS_DIR": reg_mod.MODELS_DIR,
        "reg_MODEL_BUNDLE_PATH": reg_mod.MODEL_BUNDLE_PATH,
    }
    cfg.MODELS_DIR = model_dir
    cfg.MODEL_BUNDLE_PATH = bundle
    cfg.MODEL_REGISTRY_PATH = model_dir / "registry.json"
    reg_mod.MODELS_DIR = model_dir
    reg_mod.MODEL_BUNDLE_PATH = bundle
    get_settings.cache_clear()

    from qos_anomaly.api.app import app

    with TestClient(app) as test_client:
        yield test_client

    cfg.MODELS_DIR = original["MODELS_DIR"]
    cfg.MODEL_BUNDLE_PATH = original["MODEL_BUNDLE_PATH"]
    cfg.MODEL_REGISTRY_PATH = original["MODEL_REGISTRY_PATH"]
    reg_mod.MODELS_DIR = original["reg_MODELS_DIR"]
    reg_mod.MODEL_BUNDLE_PATH = original["reg_MODEL_BUNDLE_PATH"]
    get_settings.cache_clear()


def test_health(client):
    res = client.get("/v1/health")
    assert res.status_code == 200
    assert res.json()["model_ready"] is True


def test_predict_one(client):
    payload = {
        "record": {
            "timestamp": "2026-01-15T10:30:00",
            "client_ip": "10.1.2.3",
            "endpoint_uri": "/api/v1/auth/login",
            "http_method": "POST",
            "response_time_ms": 120.0,
            "status_code": 200,
            "bytes_sent": 1500,
        }
    }
    res = client.post("/v1/predict", json=payload)
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_predict_batch(client):
    records = [
        {
            "timestamp": "2026-01-15T10:30:00",
            "client_ip": "10.1.2.3",
            "endpoint_uri": "/api/v1/accounts/balance",
            "http_method": "GET",
            "response_time_ms": 80.0,
            "status_code": 200,
            "bytes_sent": 1000,
        },
        {
            "timestamp": "2026-01-15T10:30:01",
            "client_ip": "10.1.2.3",
            "endpoint_uri": "/api/v1/transfers/napas",
            "http_method": "POST",
            "response_time_ms": 9000.0,
            "status_code": 504,
            "bytes_sent": 200,
        },
    ]
    res = client.post("/v1/predict/batch", json={"records": records})
    assert res.status_code == 200
    assert res.json()["total"] == 2
