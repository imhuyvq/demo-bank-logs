"""SQLAlchemy models cho PostgreSQL."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class DatasetLog(Base):
    __tablename__ = "dataset_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    endpoint_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    http_method: Mapped[str] = mapped_column(String(16), nullable=False)
    response_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes_sent: Mapped[int] = mapped_column(Integer, nullable=False)
    is_anomaly: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anomaly_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list["DetectionResult"]] = relationship(back_populates="log")


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_id: Mapped[int] = mapped_column(ForeignKey("dataset_logs.id"), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    is_anomaly: Mapped[bool] = mapped_column(Boolean, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    log: Mapped[DatasetLog] = relationship(back_populates="results")
