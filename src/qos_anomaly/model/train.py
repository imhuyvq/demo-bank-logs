"""Huấn luyện Isolation Forest."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler

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


def tune_isolation_forest(
    X_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
) -> tuple[IsolationForest, dict[str, Any], float, float]:
    """Grid search nhỏ trên validation F1."""
    param_grid = {
        "n_estimators": [200, 300, 500],
        "contamination": [0.04, 0.06, 0.08],
        "max_features": [0.8, 1.0],
    }
    best_model: IsolationForest | None = None
    best_params: dict[str, Any] = {}
    best_threshold = 0.0
    best_f1 = -1.0

    for n_est, contam, max_feat in product(
        param_grid["n_estimators"],
        param_grid["contamination"],
        param_grid["max_features"],
    ):
        model = IsolationForest(
            n_estimators=n_est,
            contamination=contam,
            max_features=max_feat,
            max_samples=DEFAULT_MAX_SAMPLES,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(X_train)
        val_scores = anomaly_scores(model, X_val)
        threshold, f1 = find_best_threshold(val_scores, y_val)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold
            best_params = {
                "n_estimators": n_est,
                "contamination": contam,
                "max_features": max_feat,
            }
            best_model = model

    if best_model is None:
        raise RuntimeError("Không tìm được mô hình phù hợp")

    return best_model, best_params, best_threshold, best_f1


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

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)

    y_val = val_df["is_anomaly"].values.astype(int)
    y_test = test_df["is_anomaly"].values.astype(int)

    model, best_params, threshold, val_f1 = tune_isolation_forest(X_train_s, X_val_s, y_val)

    test_scores = anomaly_scores(model, X_test_s)
    test_pred = (test_scores >= threshold).astype(int)
    test_f1 = float(f1_score(y_test, test_pred, zero_division=0))

    trained_at = datetime.now(timezone.utc).isoformat()
    bundle = {
        "model": model,
        "scaler": scaler,
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

    from qos_anomaly.model.registry import ModelRegistry

    registry = ModelRegistry(
        models_dir=output_path.parent,
        legacy_bundle_path=output_path,
    )
    version = registry.register_bundle(bundle, set_active=True)

    logger.info(
        "Đã lưu model tại %s | model_id=%s | best_params=%s | val_f1=%.4f",
        output_path,
        version.model_id,
        best_params,
        val_f1,
    )

    return {
        "output_path": str(output_path),
        "model_id": version.model_id,
        "best_params": best_params,
        "threshold": threshold,
        "val_f1": val_f1,
        "test_f1_preview": test_f1,
        "train_size": len(train_df),
        "val_size": len(val_df),
        "test_size": len(test_df),
    }
