"""
Telemetry panel: recording and inspection of per-decision metrics.

Measures and stores (rule 4 of `system_architecture.md`):
  * execution timestamp,
  * model latency in milliseconds,
  * confidence score,
and derives an aggregated summary (incl. % within the <100ms target).

Standard library only. History is kept in memory with an optional cap so it
does not grow unbounded during long sessions.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from ..config import LATENCY_TARGET_MS


@dataclass(frozen=True)
class TelemetryRecord:
    """Immutable metrics of a single evaluation."""

    timestamp: float          # Epoch (seconds) of the moment of recording.
    latency_ms: float         # Latency of the evaluation in milliseconds.
    confidence_score: float   # Confidence [0.0, 1.0] returned by the model.
    action_type: str          # Classified action type.
    target_branch: str        # Chosen narrative branch.
    triggered_fallback: bool  # Was Human-in-the-Loop triggered?

    @property
    def within_latency_target(self) -> bool:
        """True if the evaluation met the latency target (<100ms)."""
        return self.latency_ms < LATENCY_TARGET_MS


@dataclass(frozen=True)
class TelemetrySummary:
    """Aggregated view of the telemetry history."""

    total: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    last_latency_ms: float
    avg_confidence: float
    last_confidence: float
    fallback_count: int
    within_target_ratio: float  # Fraction [0.0, 1.0] under the latency target.


class TelemetryPanel:
    """Accumulates telemetry records and exposes real-time aggregates."""

    def __init__(self, max_history: Optional[int] = 1000) -> None:
        """Create the panel.

        Args:
            max_history: max number of records to keep. `None` = unlimited.
        """
        # A `deque` with `maxlen` automatically discards the oldest entries.
        self._records: Deque[TelemetryRecord] = deque(maxlen=max_history)

    def record(
        self,
        latency_ms: float,
        confidence_score: float,
        action_type: str,
        target_branch: str,
        triggered_fallback: bool,
    ) -> TelemetryRecord:
        """Record the metrics of an evaluation and return the created record."""
        entry = TelemetryRecord(
            timestamp=time.time(),
            latency_ms=latency_ms,
            confidence_score=confidence_score,
            action_type=action_type,
            target_branch=target_branch,
            triggered_fallback=triggered_fallback,
        )
        self._records.append(entry)
        return entry

    # --- History reads ------------------------------------------------------
    @property
    def records(self) -> List[TelemetryRecord]:
        """Copy of the full history (oldest to newest)."""
        return list(self._records)

    @property
    def confidence_history(self) -> List[float]:
        """History of confidence scores in chronological order."""
        return [r.confidence_score for r in self._records]

    @property
    def latency_history(self) -> List[float]:
        """History of latencies (ms) in chronological order."""
        return [r.latency_ms for r in self._records]

    def summary(self) -> Optional[TelemetrySummary]:
        """Aggregate the history. Returns `None` if there are no records yet."""
        if not self._records:
            return None

        latencies = self.latency_history
        confidences = self.confidence_history
        within_target = sum(1 for r in self._records if r.within_latency_target)
        fallbacks = sum(1 for r in self._records if r.triggered_fallback)
        total = len(self._records)

        return TelemetrySummary(
            total=total,
            avg_latency_ms=sum(latencies) / total,
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            last_latency_ms=latencies[-1],
            avg_confidence=sum(confidences) / total,
            last_confidence=confidences[-1],
            fallback_count=fallbacks,
            within_target_ratio=within_target / total,
        )

    def reset(self) -> None:
        """Clear the telemetry history."""
        self._records.clear()

    # --- Export -------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the telemetry session to a JSON-compatible dict.

        Includes export metadata, the aggregated summary and the full record
        history (with both epoch and ISO-8601 timestamps for readability).
        """
        summary = self.summary()
        records: List[Dict[str, Any]] = []
        for r in self._records:
            row = asdict(r)
            # Add derived fields useful when reading the JSON outside the process.
            row["timestamp_iso"] = datetime.fromtimestamp(
                r.timestamp, tz=timezone.utc
            ).isoformat()
            row["within_latency_target"] = r.within_latency_target
            records.append(row)

        return {
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "latency_target_ms": LATENCY_TARGET_MS,
            "summary": asdict(summary) if summary is not None else None,
            "records": records,
        }

    def export_json(self, path: Optional[str] = None, indent: int = 2) -> Path:
        """Write the telemetry session to a JSON file and return its path.

        Args:
            path: output path. If None, a timestamped name is generated in the
                current working directory.
            indent: JSON indentation for readability.

        Returns:
            The `Path` of the written file.
        """
        if path is None:
            stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = f"chronosdecider_telemetry_{stamp}.json"
        out = Path(path)
        # Create the parent directory if a nested path was given.
        if out.parent and not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        return out
