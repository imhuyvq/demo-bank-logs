"""Huấn luyện Isolation Forest."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score


from qos_anomaly.config import (
    DEFAULT_CONTAMINATION,
    DEFAULT_MAX_SAMPLES,
    DEFAULT_N_ESTIMATORS,
    FEATURE_COLUMNS,
    MODEL_BUNDLE_PATH,
    RANDOM_STATE,
    TRAIN_RATIO,
    VAL_RATIO,
    ensure_directories,
)
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.loader import load_logs

logger = logging.getLogger(__name__)


def chronological_split(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VAL_RATIO,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chia dữ liệu theo thời gian."""
    n = len(df)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    train = df.iloc[:train_end].copy()
    val = df.iloc[train_end:val_end].copy()
    test = df.iloc[val_end:].copy()
    return train, val, test


def anomaly_scores(model: IsolationForest, X: np.ndarray) -> np.ndarray:
    """Chuyển score sklearn sang hướng cao = bất thường hơn."""
    return -model.decision_function(X)


def find_best_threshold(
    scores: np.ndarray,
    y_true: np.ndarray,
    n_steps: int = 200,
) -> tuple[float, float]:
    """Tìm ngưỡng tối ưu F1 trên validation."""
    if len(scores) == 0:
        return 0.0, 0.0
    lo, hi = float(np.percentile(scores, 1)), float(np.percentile(scores, 99))
    if lo >= hi:
        hi = lo + 1e-6
    thresholds = np.linspace(lo, hi, n_steps)
    best_f1, best_t = 0.0, thresholds[0]
    for t in thresholds:
        pred = (scores >= t).astype(int)
        f1 = f1_score(y_true, pred, zero_division=0)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    return best_t, best_f1


def train_isolation_forest(
    X_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> tuple[IsolationForest, dict[str, Any], float, float]:
    """Huấn luyện một Isolation Forest, rồi chọn ngưỡng có F1 validation cao nhất."""
    params: dict[str, Any] = {
        "n_estimators": DEFAULT_N_ESTIMATORS,
        "contamination": DEFAULT_CONTAMINATION,
        "max_features": 1.0,
    }
    model = IsolationForest(
        n_estimators=DEFAULT_N_ESTIMATORS,
        contamination=DEFAULT_CONTAMINATION,
        max_features=1.0,
        max_samples=DEFAULT_MAX_SAMPLES,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    # Isolation Forest chỉ học ma trận đặc trưng, không dùng nhãn y_train.
    model.fit(X_train)
    threshold, val_f1 = find_best_threshold(anomaly_scores(model, X_val), y_val)
    return model, params, threshold, val_f1


def train_pipeline(
    data_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Huấn luyện đầy đủ và lưu bundle."""
    ensure_directories()
    output_path = Path(output_path or MODEL_BUNDLE_PATH)

    df = load_logs(data_path, require_labels=True)
    train_df, val_df, test_df = chronological_split(df)

    feature_builder = FeatureBuilder()
    feature_builder.fit(train_df)

    X_train = feature_builder.transform(train_df).values
    X_val = feature_builder.transform(val_df).values
    X_test = feature_builder.transform(test_df).values

    y_val = val_df["is_anomaly"].values.astype(int)
    y_test = test_df["is_anomaly"].values.astype(int)

    # Cây quyết định không dựa trên khoảng cách, nên không cần StandardScaler.
    model, best_params, threshold, val_f1 = train_isolation_forest(X_train, X_val, y_val)

    test_scores = anomaly_scores(model, X_test)
    test_pred = (test_scores >= threshold).astype(int)
    test_f1 = float(f1_score(y_test, test_pred, zero_division=0))

    trained_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "model": model,
        "feature_builder": feature_builder.to_dict(),
        "feature_columns": FEATURE_COLUMNS,
        "threshold": threshold,
        "best_params": best_params,
        "metrics_val": {"f1": val_f1},
        "metrics_test_preview": {"f1": test_f1},
        "trained_at": trained_at,
        "sklearn_version": __import__("sklearn").__version__,
        "default_n_estimators": DEFAULT_N_ESTIMATORS,
        "default_contamination": DEFAULT_CONTAMINATION,
    }

    joblib.dump(bundle, output_path)

    logger.info("Đã lưu model tại %s | val_f1=%.4f", output_path, val_f1)

    return {
        "output_path": str(output_path),
        "best_params": best_params,
        "threshold": threshold,
        "val_f1": val_f1,
        "test_f1_preview": test_f1,
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
    }
