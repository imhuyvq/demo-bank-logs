"""Shared Streamlit runtime helpers (cached services)."""
from __future__ import annotations

import streamlit as st

from qos_anomaly.services.detection import DetectionService


@st.cache_resource
def get_service() -> DetectionService:
    return DetectionService()
