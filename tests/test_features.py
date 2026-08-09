"""Tests for feature engineering."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import FEATURE_COLUMNS
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.generator import generate_logs


def test_feature_shape():
    df = generate_logs(n_rows=500, seed=42)
    fb = FeatureBuilder()
    X = fb.fit_transform(df)
    assert X.shape == (500, len(FEATURE_COLUMNS))
    assert list(X.columns) == FEATURE_COLUMNS


def test_no_nan_after_transform():
    df = generate_logs(n_rows=300, seed=42)
    fb = FeatureBuilder()
    X = fb.fit_transform(df)
    assert X.isna().sum().sum() == 0


def test_transform_requires_fit():
    df = generate_logs(n_rows=100, seed=42)
    fb = FeatureBuilder()
    with pytest.raises(RuntimeError):
        fb.transform(df)
