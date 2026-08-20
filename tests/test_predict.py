"""Test train rồi predict trên bundle tạm."""
from __future__ import annotations

from pathlib import Path

from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.model.predict import load_bundle, predict_dataframe
from qos_anomaly.model.train import train_pipeline


def test_predict_dataframe(tmp_path: Path) -> None:
    data_path = save_dataset(generate_logs(n_rows=800, anomaly_ratio=0.08, seed=42), tmp_path / "logs.csv")
    model_path = tmp_path / "model.joblib"
    train_pipeline(data_path, model_path)

    result = predict_dataframe(generate_logs(n_rows=50, seed=99), load_bundle(model_path))
    assert len(result) == 50
    assert {"anomaly_score", "is_anomaly_pred"} <= set(result.columns)
