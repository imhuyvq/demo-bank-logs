"""Dự đoán anomaly từ bundle đã huấn luyện."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from qos_anomaly.config import MODEL_BUNDLE_PATH
from qos_anomaly.data.features import FeatureBuilder
from qos_anomaly.data.loader import clean_logs
from qos_anomaly.model.train import anomaly_scores


def load_bundle(path: str | Path | None = None) -> dict[str, Any]:
    """Tải model bundle từ disk."""
    path = Path(path or MODEL_BUNDLE_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy model bundle: {path}. Chạy `make train` trước."
        )
    return joblib.load(path)


def predict_dataframe(
    df: pd.DataFrame,
    bundle: dict[str, Any] | None = None,
    threshold: float | None = None,
) -> pd.DataFrame:
    """Dự đoán anomaly cho DataFrame log đã làm sạch."""
    bundle = bundle or load_bundle()
    work = clean_logs(df)

    fb = FeatureBuilder.from_dict(bundle["feature_builder"])
    X = fb.transform(work).values
    # Bundle cũ có scaler; bundle mới bỏ bước này vì Isolation Forest không cần scale.
    model_input = bundle["scaler"].transform(X) if "scaler" in bundle else X
    scores = anomaly_scores(bundle["model"], model_input)

    thr = threshold if threshold is not None else bundle["threshold"]
    is_anomaly = (scores >= thr).astype(int)

    result = work.copy()
    result["anomaly_score"] = scores
    result["is_anomaly_pred"] = is_anomaly
    result["predicted_anomaly"] = is_anomaly.astype(bool)
    return result
