"""Tests for predict (requires trained model)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import MODEL_BUNDLE_PATH, SAMPLE_LOGS_PATH
from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.model.predict import predict_dataframe
from qos_anomaly.model.train import train_pipeline


@pytest.fixture(scope="module")
def trained_bundle(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    model_dir = tmp_path_factory.mktemp("models")
    csv_path = data_dir / "sample.csv"
    model_path = model_dir / "model.joblib"
    df = generate_logs(n_rows=2000, anomaly_ratio=0.08, seed=42)
    save_dataset(df, csv_path, data_dir / "sample.json")
    train_pipeline(csv_path, model_path)
    return model_path, df


def test_predict_dataframe(trained_bundle):
    model_path, df = trained_bundle
    from qos_anomaly.model.predict import load_bundle

    bundle = load_bundle(model_path)
    result = predict_dataframe(df.head(50), bundle=bundle)
    assert "anomaly_score" in result.columns
    assert "is_anomaly_pred" in result.columns
    assert len(result) == 50
