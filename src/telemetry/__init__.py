"""
ChronosDecider telemetry panel.

Captures, for each evaluation, the latency in milliseconds and the history of
confidence scores, per rule 4 of the architecture.
"""

from .telemetry_panel import TelemetryPanel, TelemetryRecord, TelemetrySummary

__all__ = ["TelemetryPanel", "TelemetryRecord", "TelemetrySummary"]
