"""Repository PostgreSQL (lưu lịch sử detection — tùy chọn)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from qos_anomaly.config import DATABASE_URL
from qos_anomaly.db.models import Base, DatasetLog, DetectionResult

logger = logging.getLogger(__name__)


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or DATABASE_URL, pool_pre_ping=True)


def init_db(engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    Base.metadata.create_all(engine)


def check_db_connection(url: str | None = None) -> bool:
    try:
        engine = get_engine(url)
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("DB không khả dụng: %s", exc)
        return False


class DetectionRepository:
    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or get_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)

    def save_detection_batch(self, logs_df: pd.DataFrame, results_df: pd.DataFrame) -> int:
        with Session(self.engine) as session:
            log_objects: list[DatasetLog] = []
            for i in range(len(logs_df)):
                row = logs_df.iloc[i]
                log_objects.append(
                    DatasetLog(
                        timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                        client_ip=str(row["client_ip"]),
                        endpoint_uri=str(row["endpoint_uri"]),
                        http_method=str(row["http_method"]),
                        response_time_ms=float(row["response_time_ms"]),
                        status_code=int(row["status_code"]),
                        bytes_sent=int(row["bytes_sent"]),
                        is_anomaly=int(row["is_anomaly"])
                        if "is_anomaly" in logs_df.columns and pd.notna(row.get("is_anomaly"))
                        else None,
                        anomaly_type=str(row["anomaly_type"])
                        if "anomaly_type" in logs_df.columns and pd.notna(row.get("anomaly_type"))
                        else None,
                    )
                )
            session.add_all(log_objects)
            session.flush()
            for i, log_obj in enumerate(log_objects):
                res_row = results_df.iloc[i]
                session.add(
                    DetectionResult(
                        log_id=log_obj.id,
                        anomaly_score=float(res_row["anomaly_score"]),
                        is_anomaly=bool(res_row["is_anomaly_pred"]),
                        predicted_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()
            return len(log_objects)

    def list_recent_results(self, limit: int = 100) -> pd.DataFrame:
        with Session(self.engine) as session:
            stmt = (
                select(
                    DetectionResult.id,
                    DatasetLog.timestamp,
                    DatasetLog.client_ip,
                    DatasetLog.endpoint_uri,
                    DatasetLog.status_code,
                    DetectionResult.anomaly_score,
                    DetectionResult.is_anomaly,
                    DetectionResult.predicted_at,
                )
                .join(DetectionResult, DetectionResult.log_id == DatasetLog.id)
                .order_by(DetectionResult.predicted_at.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).all()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(
                rows,
                columns=[
                    "id",
                    "timestamp",
                    "client_ip",
                    "endpoint_uri",
                    "status_code",
                    "anomaly_score",
                    "is_anomaly",
                    "predicted_at",
                ],
            )
