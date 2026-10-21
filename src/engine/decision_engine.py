"""
Motor de decisión de ChronosDecider.

Flujo por evaluación (cumple las 4 reglas de `system_architecture.md`):
  1. Enruta el input del jugador por Strands Decider 2B (vía `DeciderClient`).
  2. Aplica la lógica de triage: si `confidence_score <= 0.70` activa el
     fallback (Human-in-the-Loop) y genera un prompt de aclaración.
  3. Valida ESTRICTAMENTE la salida contra `narrative_schema.json`.
  4. Mide la latencia en milisegundos y registra la telemetría.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..config import CONFIDENCE_FALLBACK_THRESHOLD, LATENCY_TARGET_MS
from ..telemetry import TelemetryPanel
from .decider_client import DeciderClient
from .schema_validator import validate_narrative_output


@dataclass
class EvaluationResult:
    """Resultado completo de una evaluación, listo para la UI y la telemetría."""

    payload: Dict[str, Any]          # Salida validada conforme al esquema.
    latency_ms: float                # Latencia medida de la evaluación.
    within_latency_target: bool      # ¿Se cumplió el objetivo (<100ms)?
    clarification_prompt: Optional[str] = None  # Presente si hay fallback.

    # --- Accesores de conveniencia (leen del payload validado) --------------
    @property
    def action_type(self) -> str:
        return self.payload["action_type"]

    @property
    def target_branch(self) -> str:
        return self.payload["target_branch"]

    @property
    def confidence_score(self) -> float:
        return self.payload["confidence_score"]

    @property
    def trigger_fallback(self) -> bool:
        return self.payload["trigger_fallback"]

    @property
    def narrative_response(self) -> str:
        return self.payload["narrative_response"]


class DecisionEngine:
    """Orquesta clasificación, triage, validación y telemetría."""

    def __init__(
        self,
        decider: Optional[DeciderClient] = None,
        telemetry: Optional[TelemetryPanel] = None,
        fallback_threshold: float = CONFIDENCE_FALLBACK_THRESHOLD,
    ) -> None:
        self._decider = decider or DeciderClient()
        self._telemetry = telemetry or TelemetryPanel()
        self._fallback_threshold = fallback_threshold

    @property
    def telemetry(self) -> TelemetryPanel:
        """Panel de telemetría asociado al motor (de solo lectura externa)."""
        return self._telemetry

    def evaluate(self, player_input: str, context: Dict[str, Any] | None = None) -> EvaluationResult:
        """Evalúa una acción del jugador de principio a fin.

        Args:
            player_input: texto libre introducido por el jugador.
            context: estado narrativo opcional para el modelo.

        Returns:
            `EvaluationResult` con la salida validada, la latencia y, si procede,
            el prompt de aclaración (Human-in-the-Loop).
        """
        # Reloj monotónico: inmune a ajustes del reloj del sistema.
        start = time.perf_counter()

        # 1) Clasificación de intención vía Strands Decider 2B.
        response = self._decider.classify(player_input, context)
        payload = response.to_payload()

        # 2) Triage / Fallback (regla 3): decisión del motor, no del backend.
        confidence = float(payload.get("confidence_score", 0.0))
        clarification_prompt: Optional[str] = None
        if confidence <= self._fallback_threshold:
            payload["trigger_fallback"] = True
            clarification_prompt = self._build_clarification_prompt(player_input, confidence)
        else:
            payload["trigger_fallback"] = False

        # 4a) Latencia: se mide antes de validar para reflejar el coste real
        # de la clasificación + triage, y se adjunta al payload.
        latency_ms = (time.perf_counter() - start) * 1000.0
        payload["latency_ms"] = latency_ms

        # 3) Validación estricta contra el esquema narrativo.
        # Si la salida del modelo no cumple el esquema, se propaga el error:
        # preferimos fallar explícitamente antes que entregar datos inválidos.
        validate_narrative_output(payload)

        within_target = latency_ms < LATENCY_TARGET_MS

        # 4b) Registro de telemetría por cada evaluación.
        self._telemetry.record(
            latency_ms=latency_ms,
            confidence_score=confidence,
            action_type=payload["action_type"],
            target_branch=payload["target_branch"],
            triggered_fallback=payload["trigger_fallback"],
        )

        return EvaluationResult(
            payload=payload,
            latency_ms=latency_ms,
            within_latency_target=within_target,
            clarification_prompt=clarification_prompt,
        )

    def _build_clarification_prompt(self, player_input: str, confidence: float) -> str:
        """Genera el prompt de aclaración para el jugador (Human-in-the-Loop)."""
        shown = player_input.strip() or "(entrada vacía)"
        return (
            "No estoy seguro de cómo interpretar esa acción "
            f"(certeza {confidence:.0%}, umbral {self._fallback_threshold:.0%}). "
            f"Reformula o detalla qué quieres hacer con: \"{shown}\"."
        )
