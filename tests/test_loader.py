"""Tests for loader."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.data.loader import load_logs, validate_log_schema


def test_load_csv_json():
    df = generate_logs(n_rows=100, seed=42)
    with tempfile.TemporaryDirectory() as tmp:
        csv_p = Path(tmp) / "logs.csv"
        json_p = Path(tmp) / "logs.json"
        save_dataset(df, csv_p, json_p)
        csv_df = load_logs(csv_p)
        json_df = load_logs(json_p)
    assert len(csv_df) == 100
    assert len(json_df) == 100


def test_response_time_alias():
    df = generate_logs(n_rows=10, seed=42)
    df = df.rename(columns={"response_time_ms": "response_time"})
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        df.to_csv(f.name, index=False)
        loaded = load_logs(f.name)
    assert "response_time_ms" in loaded.columns


def test_validate_missing_column():
    df = pd.DataFrame({"timestamp": ["2025-01-01"]})
    with pytest.raises(ValueError):
        validate_log_schema(df)
