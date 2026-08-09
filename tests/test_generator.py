"""Tests for log generator."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.config import LOG_COLUMNS, LABEL_COLUMNS
from qos_anomaly.data.generator import generate_logs


def test_generate_logs_schema():
    df = generate_logs(n_rows=1000, anomaly_ratio=0.1, seed=42)
    assert len(df) == 1000
    for col in LOG_COLUMNS + LABEL_COLUMNS:
        assert col in df.columns


def test_anomaly_ratio_in_range():
    df = generate_logs(n_rows=5000, anomaly_ratio=0.06, seed=42)
    ratio = df["is_anomaly"].mean()
    assert 0.03 <= ratio <= 0.12


def test_anomaly_types():
    df = generate_logs(n_rows=3000, anomaly_ratio=0.15, seed=42)
    types = set(df["anomaly_type"].unique())
    assert "normal" in types
    assert "spam" in types or "high_latency" in types
