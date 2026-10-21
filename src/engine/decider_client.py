"""
Cliente de Strands Decider 2B: la capa de DECISIÓN de ChronosDecider.

Strands Decider 2B no genera texto. Lee un estado y una pregunta tipada y
devuelve una elección con una confianza calibrada
(https://github.com/strands-labs/strands-decider). ChronosDecider le hace una
pregunta `choice`: dada la acción del jugador, ¿qué rama narrativa corresponde?

Este módulo expone:
  * `DecisionResult`          : elección + confianza (SIN narrativa).
  * `DeciderBackend`          : interfaz que cualquier backend debe cumplir.
  * `StrandsDeciderHTTPBackend`: cliente del servidor real (`/v1/systemone`).
  * `SimulatedDeciderBackend` : fallback determinista para correr sin el modelo.
  * `DeciderClient`           : fachada estable que usa el motor.

El servidor real se levanta con:
    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000
"""

from __future__ import annotations

import json
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

# Nombre de la pregunta `choice` que enviamos al modelo.
_BRANCH_QUESTION = "narrative_branch"
_BRANCH_INSTRUCTIONS = (
    "Dada la acción del jugador, elige la rama narrativa del RPG que corresponde."
)


@dataclass
class DecisionResult:
    """Resultado de la DECISIÓN del Decider (sin texto narrativo).

    Attributes:
        branch_id: id de la rama elegida (clave de NARRATIVE_BRANCHES) o 'clarify'.
        action_type: tipo de acción asociado a la rama (p. ej. 'COMBAT').
        confidence_score: confianza calibrada [0.0, 1.0] devuelta por el modelo.
        source: de dónde salió la decisión ('strands-decider' o 'simulated').
        decision_latency_ms: latencia REAL del backend que resolvió la decisión.
            No incluye intentos fallidos de otros backends (ver DeciderClient).
        server_latency_ms: latencia reportada por el propio servidor, si existe.
        raw: respuesta cruda para depuración.
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
    """Contrato de un backend de decisión."""

    def decide_branch(self, player_input: str, options: List[str]) -> DecisionResult:
        """Elige una rama narrativa entre `options` para `player_input`."""
        ...


class StrandsDeciderHTTPBackend:
    """Backend que llama al servidor HTTP de Strands Decider 2B.

    Usa el endpoint `/v1/systemone` con una pregunta `choice`. Implementado con
    `urllib` de la biblioteca estándar: no añade dependencias.
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
        # El modelo espera `state` (el texto) y `questions` tipadas. La pregunta
        # `choice` lleva las opciones separadas por comas en `instructions`.
        body = {
            "state": player_input,
            "questions": {
                _BRANCH_QUESTION: {
                    "type": "choice",
                    "instructions": f"{_BRANCH_INSTRUCTIONS}={','.join(options)}",
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
        # Latencia medida localmente de ida y vuelta al servidor del modelo.
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - start) * 1000.0

        return self._parse(payload, options, latency_ms)

    def _parse(
        self, payload: Dict[str, Any], options: List[str], latency_ms: float
    ) -> DecisionResult:
        """Traduce la respuesta del servidor a un `DecisionResult`.

        Formato esperado (ver README oficial del servidor):
            {"answers": {"narrative_branch": {"type":"choice",
             "choice":"combat", "confidence":0.83, ...}}, "latency_ms": ...}
        Se es tolerante con variaciones menores de forma.
        """
        answers = payload.get("answers", {})
        answer = answers.get(_BRANCH_QUESTION, {})

        branch_id = answer.get("choice") or answer.get("value")
        confidence = answer.get("confidence")

        # Si el servidor devuelve distribución de probabilidades, usamos el argmax.
        if branch_id is None and isinstance(answer.get("probabilities"), dict):
            probs: Dict[str, float] = answer["probabilities"]
            branch_id = max(probs, key=probs.get)
            confidence = probs[branch_id]

        if branch_id not in NARRATIVE_BRANCHES:
            # El modelo eligió algo fuera del catálogo: tratamos como baja certeza.
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
            confidence_score=float(confidence if confidence is not None else 0.0),
            source="strands-decider",
            decision_latency_ms=latency_ms,
            server_latency_ms=payload.get("latency_ms"),
            raw=payload,
        )


class SimulatedDeciderBackend:
    """Fallback determinista por reglas (para correr SIN el servidor del modelo).

    No pretende ser el modelo: es un sustituto honesto que permite ejecutar la
    demo y los tests sin descargar pesos. Marca su origen como 'simulated'.
    """

    _INTENT_RULES = [
        (("atacar", "ataca", "golpear", "pelear", "luchar", "attack"), "combat"),
        (("huir", "escapar", "correr", "flee", "run"), "flee"),
        (("hablar", "preguntar", "decir", "talk", "speak", "ask"), "dialogue"),
        (("explorar", "mirar", "buscar", "investigar", "explore", "search"), "exploration"),
        (("usar", "abrir", "coger", "tomar", "use", "open", "take"), "interaction"),
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
            # Una sola intención clara -> alta certeza; varias -> ambigua.
            confidence = 0.92 if len(matched) == 1 else 0.58
            action_type = NARRATIVE_BRANCHES.get(branch_id, ("UNKNOWN", ""))[0]

        latency_ms = (time.perf_counter() - start) * 1000.0
        return DecisionResult(
            branch_id=branch_id, action_type=action_type,
            confidence_score=confidence, source="simulated",
            decision_latency_ms=latency_ms,
        )


class DeciderClient:
    """Fachada de decisión. Usa el servidor real y cae al simulado si falla.

    El motor solo depende de esta clase. El comportamiento por defecto intenta el
    modelo real; si el servidor no está disponible (desarrollo local sin pesos),
    degrada con transparencia al backend simulado, sin romper la demo.
    """

    def __init__(
        self,
        backend: DeciderBackend | None = None,
        allow_simulated_fallback: bool = True,
    ) -> None:
        self._explicit_backend = backend
        self._allow_fallback = allow_simulated_fallback
        self._simulated = SimulatedDeciderBackend()
        # Si no se inyecta backend, intentamos el HTTP real por defecto.
        self._primary: DeciderBackend = backend or StrandsDeciderHTTPBackend()

    def decide(self, player_input: str) -> DecisionResult:
        """Decide la rama narrativa para la acción del jugador."""
        options = list(NARRATIVE_BRANCHES.keys())
        try:
            return self._primary.decide_branch(player_input, options)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError):
            # Servidor del modelo no disponible o respuesta inesperada.
            if self._explicit_backend is not None or not self._allow_fallback:
                raise
            return self._simulated.decide_branch(player_input, options)
