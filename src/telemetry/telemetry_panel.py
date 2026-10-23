"""
Panel de telemetría: registro e inspección de métricas por decisión.

Mide y almacena (regla 4 de `system_architecture.md`):
  * timestamp de ejecución,
  * latencia del modelo en milisegundos,
  * confidence score,
y deriva un resumen agregado (incl. % dentro del objetivo <100ms).

Solo biblioteca estándar. El historial se guarda en memoria con un tope
opcional para no crecer sin límite en sesiones largas.
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
    """Métricas inmutables de una única evaluación."""

    timestamp: float          # Epoch (segundos) del momento del registro.
    latency_ms: float         # Latencia de la evaluación en milisegundos.
    confidence_score: float   # Certeza [0.0, 1.0] devuelta por el modelo.
    action_type: str          # Tipo de acción clasificada.
    target_branch: str        # Rama narrativa elegida.
    triggered_fallback: bool  # ¿Se activó Human-in-the-Loop?

    @property
    def within_latency_target(self) -> bool:
        """True si la evaluación cumplió el objetivo de latencia (<100ms)."""
        return self.latency_ms < LATENCY_TARGET_MS


@dataclass(frozen=True)
class TelemetrySummary:
    """Vista agregada del historial de telemetría."""

    total: int
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    last_latency_ms: float
    avg_confidence: float
    last_confidence: float
    fallback_count: int
    within_target_ratio: float  # Fracción [0.0, 1.0] bajo el objetivo de latencia.


class TelemetryPanel:
    """Acumula registros de telemetría y expone agregados en tiempo real."""

    def __init__(self, max_history: Optional[int] = 1000) -> None:
        """Crea el panel.

        Args:
            max_history: nº máximo de registros a conservar. `None` = ilimitado.
        """
        # `deque` con `maxlen` descarta automáticamente los más antiguos.
        self._records: Deque[TelemetryRecord] = deque(maxlen=max_history)

    def record(
        self,
        latency_ms: float,
        confidence_score: float,
        action_type: str,
        target_branch: str,
        triggered_fallback: bool,
    ) -> TelemetryRecord:
        """Registra las métricas de una evaluación y devuelve el registro creado."""
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

    # --- Lectura del historial ---------------------------------------------
    @property
    def records(self) -> List[TelemetryRecord]:
        """Copia del historial completo (del más antiguo al más reciente)."""
        return list(self._records)

    @property
    def confidence_history(self) -> List[float]:
        """Historial de puntuaciones de certeza en orden cronológico."""
        return [r.confidence_score for r in self._records]

    @property
    def latency_history(self) -> List[float]:
        """Historial de latencias (ms) en orden cronológico."""
        return [r.latency_ms for r in self._records]

    def summary(self) -> Optional[TelemetrySummary]:
        """Agrega el historial. Devuelve `None` si aún no hay registros."""
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
        """Vacía el historial de telemetría."""
        self._records.clear()

    # --- Exportación --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serializa la sesión de telemetría a un dict JSON-compatible.

        Incluye metadatos de exportación, el resumen agregado y el historial
        completo de registros (con su timestamp epoch e ISO-8601 para lectura).
        """
        summary = self.summary()
        records: List[Dict[str, Any]] = []
        for r in self._records:
            row = asdict(r)
            # Añadimos campos derivados útiles al leer el JSON fuera del proceso.
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
        """Escribe la sesión de telemetría a un archivo JSON y devuelve su ruta.

        Args:
            path: ruta de salida. Si es None, se genera un nombre con timestamp
                en el directorio de trabajo actual.
            indent: sangría del JSON para legibilidad.

        Returns:
            La ruta (`Path`) del archivo escrito.
        """
        if path is None:
            stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = f"chronosdecider_telemetry_{stamp}.json"
        out = Path(path)
        # Crea el directorio padre si se indicó una ruta anidada.
        if out.parent and not out.parent.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=indent),
            encoding="utf-8",
        )
        return out
