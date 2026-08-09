"""Tests for model registry."""
from __future__ import annotations

from pathlib import Path

import joblib
import pytest

from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.model.registry import ModelRegistry
from qos_anomaly.model.train import train_pipeline


@pytest.fixture
def trained_paths(tmp_path: Path):
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models"
    data_dir.mkdir()
    model_dir.mkdir()
    csv_path = data_dir / "sample.csv"
    legacy = model_dir / "isolation_forest_bundle.joblib"
    df = generate_logs(n_rows=1500, anomaly_ratio=0.08, seed=7)
    save_dataset(df, csv_path, data_dir / "sample.json")
    result = train_pipeline(csv_path, legacy)
    return model_dir, legacy, result["model_id"]


def test_registry_after_train(trained_paths):
    model_dir, legacy, model_id = trained_paths
    registry = ModelRegistry(models_dir=model_dir, legacy_bundle_path=legacy)
    models = registry.list_models()
    assert len(models) >= 1
    assert models[0]["model_id"] == model_id
    assert models[0]["is_active"] is True
    assert (model_dir / "versions" / f"{model_id}.joblib").exists()


def test_activate_and_load(trained_paths):
    model_dir, legacy, model_id = trained_paths
    registry = ModelRegistry(models_dir=model_dir, legacy_bundle_path=legacy)

    # Đăng ký bản copy thứ hai để test activate
    bundle = joblib.load(legacy)
    bundle["trained_at"] = "2024-01-01T00:00:00+00:00"
    other = registry.register_bundle(bundle, model_id="if-old-version", set_active=False)
    assert other.model_id == "if-old-version"

    registry.activate("if-old-version")
    active = registry.get_active_info()
    assert active is not None
    assert active.model_id == "if-old-version"
    loaded = registry.load_bundle()
    assert loaded["trained_at"] == "2024-01-01T00:00:00+00:00"

    registry.activate(model_id)
    assert registry.get_active_info().model_id == model_id


def test_legacy_auto_register(tmp_path: Path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    legacy = model_dir / "bundle.joblib"
    joblib.dump(
        {
            "threshold": 0.1,
            "trained_at": "2025-06-01T12:00:00+00:00",
            "best_params": {},
            "feature_columns": ["a"],
        },
        legacy,
    )
    registry = ModelRegistry(models_dir=model_dir, legacy_bundle_path=legacy)
    info = registry.ensure_legacy_registered()
    assert info is not None
    assert info.threshold == 0.1
    assert registry.get_active_info() is not None
    assert info.model_id.startswith("qos-forest-")
    assert info.display_name == "QoS Forest 1.0"


def test_modern_version_ids(trained_paths):
    model_dir, legacy, model_id = trained_paths
    assert model_id.startswith("qos-forest-")
    assert ModelRegistry.parse_semver(model_id) == (1, 0)

    registry = ModelRegistry(models_dir=model_dir, legacy_bundle_path=legacy)
    info = registry.get_active_info()
    assert info is not None
    assert info.display_name == "QoS Forest 1.0"
    assert info.version == "1.0"

    bundle = joblib.load(legacy)
    next_info = registry.register_bundle(bundle, set_active=True)
    assert next_info.model_id == "qos-forest-1.1"
    assert next_info.display_name == "QoS Forest 1.1"


def test_legacy_label():
    assert (
        ModelRegistry.label_for("if-20260722T025022Z")
        == "QoS Forest · 22/07/2026"
    )
