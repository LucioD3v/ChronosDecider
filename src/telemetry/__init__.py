"""
Panel de telemetría de ChronosDecider.

Captura, por cada evaluación, la latencia en milisegundos y el historial de
puntuaciones de certeza (confidence score), según la regla 4 de la arquitectura.
"""

from .telemetry_panel import TelemetryPanel, TelemetryRecord, TelemetrySummary

__all__ = ["TelemetryPanel", "TelemetryRecord", "TelemetrySummary"]
