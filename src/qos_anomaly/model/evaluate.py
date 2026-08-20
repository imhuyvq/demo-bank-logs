"""Đánh giá Isolation Forest trên tập test theo thời gian."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

from qos_anomaly.config import MODEL_BUNDLE_PATH
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.loader import load_logs
from qos_anomaly.model.predict import load_bundle
from qos_anomaly.model.train import anomaly_scores, chronological_split


def evaluate_model(
    data_path: str | Path,
    bundle_path: str | Path = MODEL_BUNDLE_PATH,
) -> dict[str, Any]:
    """Trả metric test; không ghi report hay suy diễn khả năng production."""
    bundle = load_bundle(bundle_path)
    _, _, test_df = chronological_split(load_logs(data_path, require_labels=True))
    features = FeatureBuilder.from_dict(bundle["feature_builder"]).transform(test_df).values
    scores = anomaly_scores(bundle["model"], features)
    predicted = (scores >= bundle["threshold"]).astype(int)
    actual = test_df["is_anomaly"].to_numpy(dtype=int)
    tn, fp, fn, tp = confusion_matrix(actual, predicted, labels=[0, 1]).ravel()

    return {
        "test_size": len(test_df),
        "threshold": float(bundle["threshold"]),
        "precision": float(precision_score(actual, predicted, zero_division=0)),
        "recall": float(recall_score(actual, predicted, zero_division=0)),
        "f1": float(f1_score(actual, predicted, zero_division=0)),
        "accuracy": float(accuracy_score(actual, predicted)),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
        "confusion_matrix": {"tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn)},
        "note": "Kết quả chỉ trên dữ liệu mô phỏng cùng generator; không đại diện log production.",
    }
