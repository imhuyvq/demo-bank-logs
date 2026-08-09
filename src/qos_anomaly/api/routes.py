"""FastAPI routes — predict cơ bản cho báo cáo môn học."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from qos_anomaly.api.schemas import (
    BatchPredictRequest,
    HealthResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    PredictionItem,
)
from qos_anomaly.config import get_settings
from qos_anomaly.model.registry import ModelRegistry
from qos_anomaly.services.detection import DetectionService

router = APIRouter(prefix="/v1")


def _service(model_id: str | None = None) -> DetectionService:
    return DetectionService(model_id=model_id)


def _df_to_items(df) -> list[PredictionItem]:
    items: list[PredictionItem] = []
    for row in df.to_dict(orient="records"):
        ts = row["timestamp"]
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        items.append(
            PredictionItem(
                timestamp=str(ts),
                client_ip=str(row["client_ip"]),
                endpoint_uri=str(row["endpoint_uri"]),
                http_method=str(row["http_method"]),
                response_time_ms=float(row["response_time_ms"]),
                status_code=int(row["status_code"]),
                bytes_sent=int(row["bytes_sent"]),
                anomaly_score=float(row["anomaly_score"]),
                is_anomaly_pred=int(row["is_anomaly_pred"]),
                predicted_anomaly=bool(row["predicted_anomaly"]),
            )
        )
    return items


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    registry = ModelRegistry()
    active = registry.get_active_info()
    service = _service()
    ready, message = service.check_model_ready()
    return HealthResponse(
        status="ok" if ready else "degraded",
        app_env=settings.app_env,
        model_ready=ready,
        active_model_id=active.model_id if active else None,
        message=message,
    )


@router.get("/models/active", response_model=ModelInfoResponse)
def get_active_model() -> ModelInfoResponse:
    registry = ModelRegistry()
    info = registry.get_active_info()
    if info is None:
        raise HTTPException(status_code=404, detail="Chưa có model. Chạy scripts/train_model.py")
    payload = info.to_dict()
    payload["is_active"] = True
    return ModelInfoResponse(**payload)


@router.post("/predict", response_model=PredictResponse)
def predict_one(body: PredictRequest) -> PredictResponse:
    service = _service(body.model_id)
    try:
        df, _ = service.parse_manual_record(body.record.model_dump())
        run = service.detect(
            df,
            threshold=body.threshold,
            save_to_db=body.save_to_db,
            model_id=body.model_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    active = ModelRegistry().get_active_info()
    model_id = body.model_id or (active.model_id if active else None)
    return PredictResponse(
        model_id=model_id,
        threshold=run.threshold,
        anomaly_count=run.anomaly_count,
        total=len(run.result_df),
        saved_count=run.saved_count,
        results=_df_to_items(run.result_df),
    )


@router.post("/predict/batch", response_model=PredictResponse)
def predict_batch(body: BatchPredictRequest) -> PredictResponse:
    service = _service(body.model_id)
    try:
        import pandas as pd

        from qos_anomaly.data.loader import clean_logs

        df = clean_logs(pd.DataFrame([r.model_dump() for r in body.records]))
        if df.empty:
            raise ValueError("Không còn bản ghi hợp lệ sau làm sạch")
        run = service.detect(
            df,
            threshold=body.threshold,
            save_to_db=body.save_to_db,
            model_id=body.model_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    active = ModelRegistry().get_active_info()
    model_id = body.model_id or (active.model_id if active else None)
    return PredictResponse(
        model_id=model_id,
        threshold=run.threshold,
        anomaly_count=run.anomaly_count,
        total=len(run.result_df),
        saved_count=run.saved_count,
        results=_df_to_items(run.result_df),
    )
