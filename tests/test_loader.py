"""Tests cho đọc CSV và kiểm tra schema."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from qos_anomaly.data.generator import generate_logs, save_dataset
from qos_anomaly.data.loader import load_logs, validate_log_schema


def test_load_csv(tmp_path: Path) -> None:
    path = save_dataset(generate_logs(n_rows=100, seed=42), tmp_path / "logs.csv")
    assert len(load_logs(path)) == 100


def test_response_time_alias(tmp_path: Path) -> None:
    df = generate_logs(n_rows=10, seed=42).rename(columns={"response_time_ms": "response_time"})
    path = tmp_path / "logs.csv"
    df.to_csv(path, index=False)
    assert "response_time_ms" in load_logs(path).columns


def test_reject_non_csv(tmp_path: Path) -> None:
    path = tmp_path / "logs.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="CSV"):
        load_logs(path)


def test_validate_missing_column() -> None:
    with pytest.raises(ValueError):
        validate_log_schema(pd.DataFrame({"timestamp": ["2025-01-01"]}))
