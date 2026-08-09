"""FastAPI application — QoS anomaly inference API."""
from __future__ import annotations

from fastapi import FastAPI

from qos_anomaly.api.routes import router
from qos_anomaly.config import get_settings

settings = get_settings()

app = FastAPI(
    title="QoS Anomaly Detection API",
    description=(
        "API phát hiện bất thường QoS bằng Isolation Forest. "
        "Hỗ trợ predict đơn / batch và quản lý phiên bản model."
    ),
    version="2.0.0",
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "qos-anomaly-api",
        "docs": "/docs",
        "health": "/v1/health",
        "env": settings.app_env,
    }
