"""Quản lý phiên bản model (registry trên disk)."""
from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from qos_anomaly.config import MODELS_DIR, MODEL_BUNDLE_PATH, ensure_directories

logger = logging.getLogger(__name__)


PRODUCT_NAME = "QoS Forest"
ID_PREFIX = "qos-forest-"


@dataclass
class ModelVersionInfo:
    model_id: str
    path: str
    trained_at: str
    threshold: float
    version: str = "1.0"
    display_name: str = "QoS Forest 1.0"
    best_params: dict[str, Any] = field(default_factory=dict)
    metrics_val: dict[str, Any] = field(default_factory=dict)
    metrics_test_preview: dict[str, Any] = field(default_factory=dict)
    feature_columns: list[str] = field(default_factory=list)
    sklearn_version: str | None = None
    model_type: str = "IsolationForest"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelRegistry:
    """Lưu metadata + file bundle theo model_id; hỗ trợ activate/rollback."""

    def __init__(
        self,
        models_dir: Path | None = None,
        registry_path: Path | None = None,
        legacy_bundle_path: Path | None = None,
    ) -> None:
        self.models_dir = Path(models_dir or MODELS_DIR)
        self.versions_dir = self.models_dir / "versions"
        self.registry_path = Path(registry_path or (self.models_dir / "registry.json"))
        self.legacy_bundle_path = Path(legacy_bundle_path or MODEL_BUNDLE_PATH)
        ensure_directories()
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def _empty(self) -> dict[str, Any]:
        return {"active_model_id": None, "models": []}

    def _read(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return self._empty()
        with open(self.registry_path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("active_model_id", None)
        data.setdefault("models", [])
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def parse_semver(value: str | None) -> tuple[int, int] | None:
        """Parse `1.2` / `qos-forest-1.2` → (major, minor)."""
        if not value:
            return None
        raw = value.strip()
        if raw.startswith(ID_PREFIX):
            raw = raw[len(ID_PREFIX) :]
        parts = raw.split(".")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])
        if len(parts) == 1 and parts[0].isdigit():
            return int(parts[0]), 0
        return None

    @staticmethod
    def display_name_for(version: str) -> str:
        return f"{PRODUCT_NAME} {version}"

    @classmethod
    def label_for(
        cls,
        model_id: str | None,
        *,
        display_name: str | None = None,
        version: str | None = None,
        trained_at: str | None = None,
    ) -> str:
        """Nhãn đẹp cho UI (kiểu Cursor: tên sản phẩm + phiên bản)."""
        if display_name:
            return display_name
        if version:
            return cls.display_name_for(version)
        parsed = cls.parse_semver(model_id)
        if parsed is not None:
            return cls.display_name_for(f"{parsed[0]}.{parsed[1]}")
        # Legacy if-YYYYMMDDTHHMMSSZ → QoS Forest · ngày
        if model_id and model_id.startswith("if-") and len(model_id) >= 11:
            stamp = model_id[3:11]
            if stamp.isdigit():
                return f"{PRODUCT_NAME} · {stamp[6:8]}/{stamp[4:6]}/{stamp[:4]}"
        if trained_at:
            try:
                dt = datetime.fromisoformat(trained_at.replace("Z", "+00:00"))
                return f"{PRODUCT_NAME} · {dt.strftime('%d/%m/%Y')}"
            except ValueError:
                pass
        return model_id or PRODUCT_NAME

    def next_version(self) -> str:
        """Phiên bản kế tiếp dạng 1.0, 1.1, 1.2… (chỉ đếm bản qos-forest-*)."""
        best: tuple[int, int] | None = None
        for m in self._read()["models"]:
            parsed = self.parse_semver(m.get("version")) or self.parse_semver(
                m.get("model_id")
            )
            if parsed is None:
                continue
            if best is None or parsed > best:
                best = parsed
        if best is None:
            return "1.0"
        return f"{best[0]}.{best[1] + 1}"

    def make_model_id(self, trained_at: str | None = None) -> str:
        """ID hiện đại: qos-forest-1.2 (trained_at giữ tương thích chữ ký cũ)."""
        _ = trained_at
        return f"{ID_PREFIX}{self.next_version()}"

    def _version_meta(
        self, model_id: str, *, trained_at: str | None = None
    ) -> tuple[str, str]:
        return self._version_meta_static(model_id, trained_at=trained_at)

    def ensure_legacy_registered(self) -> ModelVersionInfo | None:
        """Nếu có bundle cũ nhưng chưa có registry → đăng ký làm active."""
        data = self._read()
        if data["models"]:
            active = data.get("active_model_id")
            for m in data["models"]:
                if m["model_id"] == active:
                    return self._info_from_dict(m)
            return self._info_from_dict(data["models"][0])
        if not self.legacy_bundle_path.exists():
            return None

        bundle = joblib.load(self.legacy_bundle_path)
        trained_at = bundle.get("trained_at") or datetime.now(timezone.utc).isoformat()
        model_id = self.make_model_id(trained_at)
        version, display_name = self._version_meta(model_id, trained_at=trained_at)
        version_path = self.versions_dir / f"{model_id}.joblib"
        if not version_path.exists():
            shutil.copy2(self.legacy_bundle_path, version_path)

        info = ModelVersionInfo(
            model_id=model_id,
            path=str(version_path.relative_to(self.models_dir)),
            trained_at=trained_at,
            threshold=float(bundle.get("threshold", 0.0)),
            version=version,
            display_name=display_name,
            best_params=bundle.get("best_params", {}),
            metrics_val=bundle.get("metrics_val", {}),
            metrics_test_preview=bundle.get("metrics_test_preview", {}),
            feature_columns=list(bundle.get("feature_columns", [])),
            sklearn_version=bundle.get("sklearn_version"),
        )
        data["models"] = [info.to_dict()]
        data["active_model_id"] = model_id
        self._write(data)
        logger.info("Đã đăng ký legacy bundle thành model_id=%s", model_id)
        return info

    @staticmethod
    def _info_from_dict(m: dict[str, Any]) -> ModelVersionInfo:
        fields = ModelVersionInfo.__dataclass_fields__
        payload = {k: m[k] for k in fields if k in m}
        model_id = payload.get("model_id") or m.get("model_id", "")
        trained_at = payload.get("trained_at") or m.get("trained_at")
        if "version" not in payload or "display_name" not in payload:
            version, display_name = ModelRegistry._version_meta_static(
                model_id, trained_at=trained_at
            )
            payload.setdefault("version", version)
            payload.setdefault("display_name", display_name)
        return ModelVersionInfo(**payload)

    @staticmethod
    def _version_meta_static(
        model_id: str, *, trained_at: str | None = None
    ) -> tuple[str, str]:
        parsed = ModelRegistry.parse_semver(model_id)
        if parsed is not None:
            version = f"{parsed[0]}.{parsed[1]}"
            return version, ModelRegistry.display_name_for(version)
        return "—", ModelRegistry.label_for(model_id, trained_at=trained_at)

    def register_bundle(
        self,
        bundle: dict[str, Any],
        *,
        model_id: str | None = None,
        set_active: bool = True,
    ) -> ModelVersionInfo:
        """Lưu bundle vào versions/ và cập nhật registry."""
        trained_at = bundle.get("trained_at") or datetime.now(timezone.utc).isoformat()
        model_id = model_id or self.make_model_id(trained_at)
        version, display_name = self._version_meta(model_id, trained_at=trained_at)
        version_path = self.versions_dir / f"{model_id}.joblib"
        joblib.dump(bundle, version_path)

        # Đồng bộ path legacy khi model này được đặt active
        if set_active:
            joblib.dump(bundle, self.legacy_bundle_path)

        info = ModelVersionInfo(
            model_id=model_id,
            path=str(version_path.relative_to(self.models_dir)),
            trained_at=trained_at,
            threshold=float(bundle["threshold"]),
            version=version,
            display_name=display_name,
            best_params=bundle.get("best_params", {}),
            metrics_val=bundle.get("metrics_val", {}),
            metrics_test_preview=bundle.get("metrics_test_preview", {}),
            feature_columns=list(bundle.get("feature_columns", [])),
            sklearn_version=bundle.get("sklearn_version"),
        )

        data = self._read()
        models = [m for m in data["models"] if m["model_id"] != model_id]
        models.insert(0, info.to_dict())
        data["models"] = models
        if set_active:
            data["active_model_id"] = model_id
        self._write(data)
        logger.info("Đã đăng ký model_id=%s (active=%s)", model_id, set_active)
        return info

    def list_models(self) -> list[dict[str, Any]]:
        self.ensure_legacy_registered()
        data = self._read()
        active = data.get("active_model_id")
        out = []
        for m in data["models"]:
            item = dict(m)
            item["is_active"] = item["model_id"] == active
            out.append(item)
        return out

    def get_info(self, model_id: str) -> ModelVersionInfo | None:
        self.ensure_legacy_registered()
        for m in self._read()["models"]:
            if m["model_id"] == model_id:
                return self._info_from_dict(m)
        return None

    def get_active_info(self) -> ModelVersionInfo | None:
        self.ensure_legacy_registered()
        data = self._read()
        active = data.get("active_model_id")
        if not active:
            return None
        for m in data["models"]:
            if m["model_id"] == active:
                return self._info_from_dict(m)
        return None

    def resolve_path(self, model_id: str | None = None) -> Path:
        self.ensure_legacy_registered()
        info = self.get_info(model_id) if model_id else self.get_active_info()
        if info is None:
            if self.legacy_bundle_path.exists():
                return self.legacy_bundle_path
            raise FileNotFoundError(
                "Không có model active. Chạy `make train` để tạo model."
            )
        path = self.models_dir / info.path
        if not path.exists():
            raise FileNotFoundError(f"Thiếu file bundle: {path}")
        return path

    def load_bundle(self, model_id: str | None = None) -> dict[str, Any]:
        path = self.resolve_path(model_id)
        return joblib.load(path)

    def activate(self, model_id: str) -> ModelVersionInfo:
        info = self.get_info(model_id)
        if info is None:
            raise KeyError(f"Không tìm thấy model_id={model_id}")
        path = self.models_dir / info.path
        if not path.exists():
            raise FileNotFoundError(f"Thiếu file bundle: {path}")

        data = self._read()
        data["active_model_id"] = model_id
        self._write(data)
        shutil.copy2(path, self.legacy_bundle_path)
        logger.info("Đã kích hoạt model_id=%s", model_id)
        return info
