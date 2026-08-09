"""Business logic layer — tách khỏi UI và CLI."""
from qos_anomaly.services.detection import DetectionRunResult, DetectionService

__all__ = ["DetectionRunResult", "DetectionService"]
