"""Service phát hiện bất thường — dùng chung Streamlit / CLI / API."""
from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd

from qos_anomaly.config import Settings, get_settings
from qos_anomaly.data.loader import clean_logs
from qos_anomaly.db.repository import DetectionRepository, check_db_connection, init_db
from qos_anomaly.model.predict import predict_dataframe
from qos_anomaly.model.registry import ModelRegistry
from qos_anomaly.services.data_quality import assess_data_quality


@dataclass
class DetectionRunResult:
    input_df: pd.DataFrame
    result_df: pd.DataFrame
    threshold: float
    anomaly_count: int
    model_id: str | None = None
    saved_count: int | None = None


class DetectionService:
    def __init__(
        self,
        settings: Settings | None = None,
        model_id: str | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_id = model_id
        self.registry = registry or ModelRegistry(
            models_dir=self.settings.models_dir,
            registry_path=self.settings.model_registry_path,
            legacy_bundle_path=self.settings.model_bundle_path,
        )
        self._bundle: dict[str, Any] | None = None
        self._loaded_model_id: str | None = None

    def get_bundle(self, model_id: str | None = None) -> dict[str, Any]:
        target_id = model_id if model_id is not None else self.model_id
        if self._bundle is None or self._loaded_model_id != target_id:
            self._bundle = self.registry.load_bundle(target_id)
            active = self.registry.get_active_info()
            self._loaded_model_id = target_id or (active.model_id if active else None)
        return self._bundle

    def check_model_ready(self) -> tuple[bool, str]:
        try:
            self.get_bundle()
            info = self.registry.get_active_info()
            if info:
                label = self.registry.label_for(
                    info.model_id,
                    display_name=getattr(info, "display_name", None),
                    version=getattr(info, "version", None),
                    trained_at=info.trained_at,
                )
            else:
                label = self.model_id or "unknown"
            return True, f"Mô hình sẵn sàng · {label}"
        except Exception as exc:
            return False, str(exc)

    def parse_upload(self, filename: str, content: bytes) -> tuple[pd.DataFrame, int]:
        name = filename.lower()
        buffer = BytesIO(content)
        if name.endswith(".csv"):
            raw_df = pd.read_csv(buffer)
        elif name.endswith(".json"):
            data = json.load(buffer)
            if isinstance(data, dict) and "records" in data:
                raw_df = pd.DataFrame(data["records"])
            else:
                raw_df = pd.DataFrame(data)
        else:
            raise ValueError("Chỉ hỗ trợ CSV hoặc JSON")
        return clean_logs(raw_df), len(raw_df)

    def parse_manual_record(self, record: dict[str, Any]) -> tuple[pd.DataFrame, int]:
        return clean_logs(pd.DataFrame([record])), 1

    def assess_quality(self, df: pd.DataFrame, raw_row_count: int) -> dict[str, Any]:
        return assess_data_quality(df, raw_row_count)

    def detect(
        self,
        df: pd.DataFrame,
        *,
        threshold: float | None = None,
        save_to_db: bool = False,
        model_id: str | None = None,
    ) -> DetectionRunResult:
        target_id = model_id if model_id is not None else self.model_id
        bundle = self.get_bundle(target_id)
        effective_threshold = threshold if threshold is not None else bundle["threshold"]
        result_df = predict_dataframe(df, bundle=bundle, threshold=effective_threshold)
        anomaly_count = int(result_df["is_anomaly_pred"].sum())

        saved_count: int | None = None
        if save_to_db:
            if not check_db_connection(self.settings.database_url):
                raise ConnectionError("PostgreSQL không khả dụng")
            init_db()
            saved_count = DetectionRepository().save_detection_batch(df, result_df)

        active = self.registry.get_active_info()
        resolved_id = target_id or (active.model_id if active else None)
        return DetectionRunResult(
            input_df=df,
            result_df=result_df,
            threshold=effective_threshold,
            anomaly_count=anomaly_count,
            model_id=resolved_id,
            saved_count=saved_count,
        )

    def get_model_info(self) -> dict[str, Any]:
        info = self.registry.get_active_info()
        bundle = self.get_bundle()
        base = {
            "model_type": "IsolationForest",
            "bundle_path": str(self.registry.resolve_path(self.model_id)),
            "threshold": bundle.get("threshold"),
            "trained_at": bundle.get("trained_at"),
            "sklearn_version": bundle.get("sklearn_version"),
            "best_params": bundle.get("best_params", {}),
            "feature_columns": bundle.get("feature_columns", []),
            "metrics_val": bundle.get("metrics_val", {}),
            "metrics_test_preview": bundle.get("metrics_test_preview", {}),
        }
        if info:
            base["model_id"] = info.model_id
            base["version"] = getattr(info, "version", None)
            base["display_name"] = self.registry.label_for(
                info.model_id,
                display_name=getattr(info, "display_name", None),
                version=getattr(info, "version", None),
                trained_at=info.trained_at,
            )
        return base

    def get_eval_summary(self) -> dict[str, Any] | None:
        path = self.settings.eval_report_path
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def list_history(self, limit: int | None = None) -> pd.DataFrame:
        limit = limit or self.settings.history_limit
        if not check_db_connection(self.settings.database_url):
            raise ConnectionError("PostgreSQL không khả dụng")
        init_db()
        return DetectionRepository().list_recent_results(limit=limit)

    def check_db(self) -> bool:
        return check_db_connection(self.settings.database_url)
