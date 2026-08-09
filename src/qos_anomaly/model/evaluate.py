"""Đánh giá mô hình: metrics, hiệu năng, khả thi."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

from qos_anomaly.config import EVAL_REPORT_PATH, MODEL_BUNDLE_PATH, ensure_directories
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.loader import load_logs
from qos_anomaly.model.predict import load_bundle
from qos_anomaly.model.train import anomaly_scores, chronological_split

logger = logging.getLogger(__name__)


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fpr),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def _per_type_recall(df: pd.DataFrame, pred_col: str = "is_anomaly_pred") -> dict[str, float]:
    if "anomaly_type" not in df.columns:
        return {}
    out: dict[str, float] = {}
    for atype in df["anomaly_type"].unique():
        if atype == "normal":
            continue
        mask = df["anomaly_type"] == atype
        if mask.sum() == 0:
            continue
        y_true = df.loc[mask, "is_anomaly"].values.astype(int)
        y_pred = df.loc[mask, pred_col].values.astype(int)
        out[atype] = float(recall_score(y_true, y_pred, zero_division=0))
    return out


def benchmark_inference(bundle: dict[str, Any], X_scaled: np.ndarray) -> dict[str, float]:
    model = bundle["model"]
    n = len(X_scaled)
    if n == 0:
        return {
            "inference_ms_per_1k_rows": 0.0,
            "inference_ms_per_10k_rows": 0.0,
            "throughput_rows_per_second": 0.0,
        }

    _ = anomaly_scores(model, X_scaled[: min(100, n)])

    def _time_predict(sample: np.ndarray) -> float:
        start = time.perf_counter()
        _ = anomaly_scores(model, sample)
        return (time.perf_counter() - start) * 1000

    idx_1k = min(1000, n)
    idx_10k = min(10000, n)
    ms_1k = _time_predict(X_scaled[:idx_1k])
    ms_10k = _time_predict(X_scaled[:idx_10k])
    ms_per_row = ms_10k / idx_10k if idx_10k else 0
    throughput = 1000.0 / ms_per_row if ms_per_row > 0 else 0.0

    return {
        "inference_ms_per_1k_rows": round(ms_1k * (1000 / idx_1k), 4),
        "inference_ms_per_10k_rows": round(ms_10k * (10000 / idx_10k), 4),
        "throughput_rows_per_second": round(throughput, 2),
    }


def evaluate_model(
    data_path: str | Path,
    bundle_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Đánh giá Isolation Forest trên test set."""
    ensure_directories()
    bundle_path = Path(bundle_path or MODEL_BUNDLE_PATH)
    output_path = Path(output_path or EVAL_REPORT_PATH)

    bundle = load_bundle(bundle_path)
    df = load_logs(data_path, require_labels=True)
    _, _, test_df = chronological_split(df)

    fb = FeatureBuilder.from_dict(bundle["feature_builder"])
    X_test = fb.transform(test_df).values
    X_test_s = bundle["scaler"].transform(X_test)
    y_test = test_df["is_anomaly"].values.astype(int)

    scores = anomaly_scores(bundle["model"], X_test_s)
    threshold = bundle["threshold"]
    pred = (scores >= threshold).astype(int)

    result_df = test_df.copy()
    result_df["anomaly_score"] = scores
    result_df["is_anomaly_pred"] = pred

    metrics = _classification_metrics(y_test, pred)
    per_type = _per_type_recall(result_df)
    performance = benchmark_inference(bundle, X_test_s)

    feasible = metrics["f1"] >= 0.70 and (
        performance["inference_ms_per_10k_rows"] < 500 or len(test_df) < 1000
    )
    pilot_rec = (
        "Mô hình đạt ngưỡng F1 phù hợp demo/báo cáo môn học; nên xác thực thêm trên log production."
        if feasible
        else "Cần tinh chỉnh thêm threshold/features hoặc thu thập log thực trước khi pilot."
    )

    report: dict[str, Any] = {
        "model": "IsolationForest",
        "test_size": len(test_df),
        "threshold": threshold,
        "best_params": bundle.get("best_params", {}),
        "metrics": metrics,
        "per_anomaly_type_recall": per_type,
        "performance": performance,
        "feasibility": {
            "feasible_for_pilot": feasible,
            "criteria": {"f1_min": 0.70, "inference_ms_per_10k_max": 500},
            "pilot_recommendation": pilot_rec,
        },
        "note": "Đánh giá trên dataset mô phỏng offline; cần xác thực trên log production.",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Báo cáo đánh giá: F1=%.4f | feasible=%s", metrics["f1"], feasible)
    return report
