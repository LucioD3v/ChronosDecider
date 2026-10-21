"""
Motor de decisión de ChronosDecider.

Flujo por turno (cumple las 4 reglas de `system_architecture.md` y separa
decisión de generación):

  1. DECISIÓN: Strands Decider 2B elige la rama narrativa (pregunta `choice`) y
     devuelve una confianza calibrada. Aquí se mide la latencia de la decisión.
  2. TRIAGE: si `confidence_score <= 0.70` se activa el fallback (Human-in-the-Loop):
     NO se narra, se pide aclaración.
  3. GENERACIÓN: si la confianza es suficiente, Amazon Bedrock narra la rama.
  4. VALIDACIÓN + TELEMETRÍA: la salida se valida contra el esquema y se registra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..config import CONFIDENCE_FALLBACK_THRESHOLD, LATENCY_TARGET_MS
from ..telemetry import TelemetryPanel
from .decider_client import DeciderClient, DecisionResult
from .narrator import Narrator, build_default_narrator
from .schema_validator import validate_narrative_output


@dataclass
class EvaluationResult:
    """Resultado completo de un turno, listo para la UI y la telemetría."""

    payload: Dict[str, Any]              # Salida validada conforme al esquema.
    decision_latency_ms: float           # Latencia SOLO de la decisión (objetivo <100ms).
    within_latency_target: bool          # ¿La decisión cumplió el objetivo?
    decision_source: str                 # 'strands-decider' o 'simulated'.
    narrative_source: str                # 'bedrock' o 'template'.
    clarification_prompt: Optional[str] = None  # Presente si hay fallback.

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
    """Orquesta decisión (Decider), triage, generación (Bedrock) y telemetría."""

    def __init__(
        self,
        decider: Optional[DeciderClient] = None,
        narrator: Optional[Narrator] = None,
        telemetry: Optional[TelemetryPanel] = None,
        fallback_threshold: float = CONFIDENCE_FALLBACK_THRESHOLD,
    ) -> None:
        self._decider = decider or DeciderClient()
        self._narrator = narrator or build_default_narrator()
        self._telemetry = telemetry or TelemetryPanel()
        self._fallback_threshold = fallback_threshold

    @property
    def telemetry(self) -> TelemetryPanel:
        return self._telemetry

    def evaluate(self, player_input: str) -> EvaluationResult:
        """Procesa un turno completo: decidir → triage → narrar → validar."""
        # 1) DECISIÓN. La latencia relevante (objetivo <100ms) es la del backend
        # que efectivamente resolvió, reportada en el propio DecisionResult. No la
        # cronometramos aquí para no contaminarla con posibles intentos de fallback.
        decision: DecisionResult = self._decider.decide(player_input)
        decision_latency_ms = decision.decision_latency_ms

        confidence = float(decision.confidence_score)

        # 2) TRIAGE / FALLBACK (regla 3).
        clarification_prompt: Optional[str] = None
        trigger_fallback = confidence <= self._fallback_threshold

        if trigger_fallback:
            # No narramos una decisión poco fiable: pedimos aclaración.
            target_branch = "branch.clarify"
            narrative_response = ""
            narrative_source = "none"
            clarification_prompt = self._build_clarification_prompt(player_input, confidence)
        else:
            # 3) GENERACIÓN con Bedrock (o plantilla de fallback).
            target_branch = f"branch.{decision.branch_id}"
            narrative_response = self._narrator.narrate(
                player_input, decision.branch_id, decision.action_type
            )
            narrative_source = self._narrator.source

        # 4) Construir y VALIDAR el payload contra el esquema narrativo.
        payload: Dict[str, Any] = {
            "action_type": decision.action_type,
            "target_branch": target_branch,
            "confidence_score": confidence,
            "trigger_fallback": trigger_fallback,
            "narrative_response": narrative_response,
            "latency_ms": decision_latency_ms,
        }
        validate_narrative_output(payload)

        within_target = decision_latency_ms < LATENCY_TARGET_MS

        # 4b) TELEMETRÍA por turno.
        self._telemetry.record(
            latency_ms=decision_latency_ms,
            confidence_score=confidence,
            action_type=decision.action_type,
            target_branch=target_branch,
            triggered_fallback=trigger_fallback,
        )

        return EvaluationResult(
            payload=payload,
            decision_latency_ms=decision_latency_ms,
            within_latency_target=within_target,
            decision_source=decision.source,
            narrative_source=narrative_source,
            clarification_prompt=clarification_prompt,
        )

    def _build_clarification_prompt(self, player_input: str, confidence: float) -> str:
        """Genera el prompt de aclaración (Human-in-the-Loop)."""
        shown = player_input.strip() or "(entrada vacía)"
        return (
            "No estoy seguro de cómo interpretar esa acción "
            f"(certeza {confidence:.0%}, umbral {self._fallback_threshold:.0%}). "
            f"Reformula o detalla qué quieres hacer con: \"{shown}\"."
        )
