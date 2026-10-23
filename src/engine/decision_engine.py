"""
ChronosDecider decision engine.

Per-turn flow (satisfies the 4 rules of `system_architecture.md` and separates
decision from generation):

  1. DECISION: Strands Decider 2B picks the narrative branch (`choice` question)
     and returns a calibrated confidence. Decision latency is measured here.
  2. TRIAGE: if `confidence_score <= 0.70` the fallback (Human-in-the-Loop) is
     triggered: it does NOT narrate, it asks for clarification.
  3. GENERATION: if confidence is sufficient, Amazon Bedrock narrates the branch.
  4. VALIDATION + TELEMETRY: the output is validated against the schema and logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..config import CONFIDENCE_FALLBACK_THRESHOLD, LATENCY_TARGET_MS
from ..telemetry import TelemetryPanel
from .decider_client import DeciderClient, DecisionResult
from .narrator import Narrator, TemplateNarrator, build_default_narrator
from .schema_validator import validate_narrative_output


@dataclass
class EvaluationResult:
    """Complete result of a turn, ready for the UI and telemetry."""

    payload: Dict[str, Any]              # Output validated against the schema.
    decision_latency_ms: float           # Local round-trip latency of the decision.
    within_latency_target: bool          # Did the local latency meet the target?
    decision_source: str                 # 'strands-decider' or 'simulated'.
    narrative_source: str                # 'bedrock' or 'template'.
    clarification_prompt: Optional[str] = None  # Present if there is a fallback.
    server_latency_ms: Optional[float] = None   # Model compute time reported by the server.

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
    """Orchestrates decision (Decider), triage, generation (Bedrock) and telemetry."""

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
        # Last-resort narrator, always available, for resilience in case the
        # primary narrator raises at runtime.
        self._fallback_narrator = TemplateNarrator()

    @property
    def telemetry(self) -> TelemetryPanel:
        return self._telemetry

    def evaluate(self, player_input: str) -> EvaluationResult:
        """Process a full turn: decide -> triage -> narrate -> validate."""
        # 1) DECISION. The relevant latency (target <100ms) is that of the backend
        # that actually resolved, reported in the DecisionResult itself. We do not
        # time it here so it is not contaminated by possible fallback attempts.
        decision: DecisionResult = self._decider.decide(player_input)
        decision_latency_ms = decision.decision_latency_ms

        confidence = float(decision.confidence_score)

        # 2) TRIAGE / FALLBACK (rule 3).
        clarification_prompt: Optional[str] = None
        trigger_fallback = confidence <= self._fallback_threshold

        if trigger_fallback:
            # We do not narrate an unreliable decision: we ask for clarification.
            target_branch = "branch.clarify"
            narrative_response = ""
            narrative_source = "none"
            clarification_prompt = self._build_clarification_prompt(player_input, confidence)
        else:
            # 3) GENERATION with Bedrock (or template fallback).
            # Resilience: if the narrator fails at runtime (e.g. Bedrock raises on
            # throttling or credentials), we do NOT crash the turn; we degrade to
            # a local template narration and flag it in the source.
            target_branch = f"branch.{decision.branch_id}"
            try:
                narrative_response = self._narrator.narrate(
                    player_input, decision.branch_id, decision.action_type
                )
                narrative_source = self._narrator.source
            except Exception:
                narrative_response = self._fallback_narrator.narrate(
                    player_input, decision.branch_id, decision.action_type
                )
                narrative_source = f"{getattr(self._narrator, 'source', 'unknown')}->template(error)"

        # 4) Build and VALIDATE the payload against the narrative schema.
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

        # 4b) TELEMETRY per turn.
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
            server_latency_ms=decision.server_latency_ms,
        )

    def _build_clarification_prompt(self, player_input: str, confidence: float) -> str:
        """Build the clarification prompt (Human-in-the-Loop)."""
        shown = player_input.strip() or "(empty input)"
        return (
            "I'm not sure how to interpret that action "
            f"(confidence {confidence:.0%}, threshold {self._fallback_threshold:.0%}). "
            f"Rephrase or add detail about what you want to do with: \"{shown}\"."
        )
