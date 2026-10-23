"""
Strands Decider 2B client: the DECISION layer of ChronosDecider.

Strands Decider 2B does not generate text. It reads a state and a typed question
and returns a choice with a calibrated confidence
(https://github.com/strands-labs/strands-decider). ChronosDecider asks it a
`choice` question: given the player's action, which narrative branch applies?

This module exposes:
  * `DecisionResult`           : choice + confidence (WITHOUT narrative).
  * `DeciderBackend`           : interface any backend must satisfy.
  * `StrandsDeciderHTTPBackend`: client for the real server (`/v1/systemone`).
  * `SimulatedDeciderBackend`  : deterministic fallback to run without the model.
  * `DeciderClient`            : stable facade used by the engine.

The real server is started with:
    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, runtime_checkable

from ..config import (
    DECIDER_MODEL_ID,
    DECIDER_SERVER_URL,
    DECIDER_SYSTEMONE_PATH,
    DECIDER_TIMEOUT_S,
    NARRATIVE_BRANCHES,
)

# Name of the `choice` question we send to the model.
_BRANCH_QUESTION = "narrative_branch"
_BRANCH_INSTRUCTIONS = (
    "Given the player's action, choose the matching RPG narrative branch."
)


def _safe_confidence(value: Any) -> float:
    """Normalize a possibly malformed confidence_score to [0.0, 1.0].

    Resilience: a model response with a None, non-numeric, NaN, infinite or
    out-of-range confidence must NOT propagate an exception. It collapses to a
    safe value that, being low, triggers the Human-in-the-Loop fallback.
    """
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(conf) or math.isinf(conf):
        return 0.0
    # Clamp to the valid range instead of rejecting: a 1.2 is treated as 1.0.
    return max(0.0, min(1.0, conf))


def _safe_latency(value: Any) -> float | None:
    """Normalize the latency reported by the server; None if invalid."""
    if value is None:
        return None
    try:
        lat = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(lat) or math.isinf(lat) or lat < 0:
        return None
    return lat


@dataclass
class DecisionResult:
    """Result of the Decider's DECISION (no narrative text).

    Attributes:
        branch_id: id of the chosen branch (a NARRATIVE_BRANCHES key) or 'clarify'.
        action_type: action type associated with the branch (e.g. 'COMBAT').
        confidence_score: calibrated confidence [0.0, 1.0] returned by the model.
        source: where the decision came from ('strands-decider' or 'simulated').
        decision_latency_ms: REAL latency of the backend that resolved the
            decision. Excludes failed attempts by other backends (see DeciderClient).
        server_latency_ms: latency reported by the server itself, if present.
        raw: raw response for debugging.
    """

    branch_id: str
    action_type: str
    confidence_score: float
    source: str
    decision_latency_ms: float = 0.0
    server_latency_ms: float | None = None
    raw: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DeciderBackend(Protocol):
    """Contract for a decision backend."""

    def decide_branch(self, player_input: str, options: List[str]) -> DecisionResult:
        """Choose a narrative branch among `options` for `player_input`."""
        ...


class StrandsDeciderHTTPBackend:
    """Backend that calls the Strands Decider 2B HTTP server.

    Uses the `/v1/systemone` endpoint with a `choice` question. Implemented with
    the standard-library `urllib`: it adds no dependencies.
    """

    def __init__(
        self,
        base_url: str = DECIDER_SERVER_URL,
        model_id: str = DECIDER_MODEL_ID,
        timeout_s: float = DECIDER_TIMEOUT_S,
    ) -> None:
        self._url = base_url.rstrip("/") + DECIDER_SYSTEMONE_PATH
        self._model_id = model_id
        self._timeout_s = timeout_s

    def decide_branch(self, player_input: str, options: List[str]) -> DecisionResult:
        # The model expects `state` (the text) and typed `questions`. A `choice`
        # question needs a `criteria` dict mapping each option label to a short
        # description; we build it from NARRATIVE_BRANCHES so the model gets
        # meaningful context for every branch.
        criteria = {
            opt: NARRATIVE_BRANCHES.get(opt, ("", opt))[1] for opt in options
        }
        body = {
            "state": player_input,
            "questions": {
                _BRANCH_QUESTION: {
                    "type": "choice",
                    "instructions": _BRANCH_INSTRUCTIONS,
                    "criteria": criteria,
                }
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Round-trip latency to the model server, measured locally.
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - start) * 1000.0

        return self._parse(payload, options, latency_ms)

    def _parse(
        self, payload: Dict[str, Any], options: List[str], latency_ms: float
    ) -> DecisionResult:
        """Translate the server response into a `DecisionResult`.

        Expected shape (see the server's official README):
            {"answers": {"narrative_branch": {"type":"choice",
             "choice":"combat", "confidence":0.83, ...}}, "latency_ms": ...}
        It tolerates minor shape variations.
        """
        answers = payload.get("answers", {})
        answer = answers.get(_BRANCH_QUESTION, {})

        branch_id = answer.get("choice") or answer.get("value")
        confidence = answer.get("confidence")

        # If the server returns a probability distribution, take the argmax.
        if branch_id is None and isinstance(answer.get("probabilities"), dict):
            probs: Dict[str, float] = answer["probabilities"]
            branch_id = max(probs, key=probs.get)
            confidence = probs[branch_id]

        if branch_id not in NARRATIVE_BRANCHES:
            # The model chose something outside the catalog: treat as low confidence.
            return DecisionResult(
                branch_id="clarify",
                action_type="UNKNOWN",
                confidence_score=0.0,
                source="strands-decider",
                decision_latency_ms=latency_ms,
                server_latency_ms=payload.get("latency_ms"),
                raw=payload,
            )

        action_type = NARRATIVE_BRANCHES[branch_id][0]
        return DecisionResult(
            branch_id=branch_id,
            action_type=action_type,
            confidence_score=_safe_confidence(confidence),
            source="strands-decider",
            decision_latency_ms=latency_ms,
            server_latency_ms=_safe_latency(payload.get("latency_ms")),
            raw=payload,
        )


class SimulatedDeciderBackend:
    """Deterministic rule-based fallback (to run WITHOUT the model server).

    It does not pretend to be the model: it is an honest stand-in that lets the
    demo and tests run without downloading weights. It marks its source as
    'simulated'. Keywords cover both Spanish and English player inputs.
    """

    _INTENT_RULES = [
        (("atacar", "ataca", "golpear", "pelear", "luchar", "attack", "fight", "hit"), "combat"),
        (("huir", "escapar", "correr", "flee", "run", "escape"), "flee"),
        (("hablar", "preguntar", "decir", "talk", "speak", "ask", "say"), "dialogue"),
        (("explorar", "mirar", "buscar", "investigar", "explore", "search", "look", "investigate"), "exploration"),
        (("usar", "abrir", "coger", "tomar", "use", "open", "take", "grab"), "interaction"),
    ]

    def decide_branch(self, player_input: str, options: List[str]) -> DecisionResult:
        start = time.perf_counter()
        text = (player_input or "").strip().lower()
        tokens = set(text.replace(",", " ").replace(".", " ").split()) if text else set()
        matched = [b for kws, b in self._INTENT_RULES if tokens.intersection(kws)]

        if not text:
            branch_id, action_type, confidence = "clarify", "UNKNOWN", 0.0
        elif not matched:
            branch_id, action_type, confidence = "clarify", "UNKNOWN", 0.40
        else:
            branch_id = matched[0]
            # A single clear intent -> high confidence; several -> ambiguous.
            confidence = 0.92 if len(matched) == 1 else 0.58
            action_type = NARRATIVE_BRANCHES.get(branch_id, ("UNKNOWN", ""))[0]

        latency_ms = (time.perf_counter() - start) * 1000.0
        return DecisionResult(
            branch_id=branch_id, action_type=action_type,
            confidence_score=confidence, source="simulated",
            decision_latency_ms=latency_ms,
        )


class DeciderClient:
    """Decision facade. Uses the real server and falls back to the simulated one.

    The engine only depends on this class. The default behavior tries the real
    model; if the server is unavailable (local development without weights), it
    degrades transparently to the simulated backend without breaking the demo.
    """

    def __init__(
        self,
        backend: DeciderBackend | None = None,
        allow_simulated_fallback: bool = True,
    ) -> None:
        self._explicit_backend = backend
        self._allow_fallback = allow_simulated_fallback
        self._simulated = SimulatedDeciderBackend()
        # If no backend is injected, we try the real HTTP one by default.
        self._primary: DeciderBackend = backend or StrandsDeciderHTTPBackend()

    def decide(self, player_input: str) -> DecisionResult:
        """Decide the narrative branch for the player's action.

        Resilience: if the primary backend fails for ANY reason (server down,
        timeout, malformed JSON, unexpected response shape), it degrades to the
        simulated backend instead of propagating and crashing the UI. The only
        exception is when the user injected an explicit backend or disabled the
        fallback: then the error propagates so it is not hidden in tests.
        """
        options = list(NARRATIVE_BRANCHES.keys())
        try:
            result = self._primary.decide_branch(player_input, options)
        except Exception:
            if self._explicit_backend is not None or not self._allow_fallback:
                raise
            return self._simulated.decide_branch(player_input, options)

        # Extra shielding: if the backend returned an inconsistent decision
        # (branch outside the catalog, malformed confidence), we sanitize it to
        # a low-confidence decision that triggers the Human-in-the-Loop fallback.
        return self._sanitize(result)

    @staticmethod
    def _sanitize(result: DecisionResult) -> DecisionResult:
        """Ensure the DecisionResult is consistent and safe to use.

        `clarify` is a legitimate branch (the explicit "not reliable" signal), so
        it is respected. Any OTHER branch outside the catalog is redirected to
        `clarify` with confidence 0.0 to force the fallback safely.
        """
        result.confidence_score = _safe_confidence(result.confidence_score)
        if result.branch_id != "clarify" and result.branch_id not in NARRATIVE_BRANCHES:
            result.branch_id = "clarify"
            result.action_type = "UNKNOWN"
            result.confidence_score = 0.0
        return result
