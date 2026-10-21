"""
Adaptador de integración con el modelo Strands Decider 2B.

La arquitectura exige que todo input del jugador se enrute por Strands Decider 2B
(regla 1), pero NO define endpoint, SDK, credenciales ni formato de transporte
del modelo. Para cumplir el requisito de "sin dependencias no especificadas" y
"libre de alucinaciones", este módulo expone:

  * `DeciderBackend`  : interfaz (Protocol) que cualquier backend real debe cumplir.
  * `SimulatedDeciderBackend` : backend determinista basado en reglas, usado por
    defecto para que el sistema funcione end-to-end sin el modelo real.
  * `DeciderClient`   : fachada estable que el resto del motor consume.

Cuando el modelo real esté disponible, basta con implementar un backend que
cumpla `DeciderBackend` y pasarlo a `DeciderClient` (ver el TODO más abajo).
La lógica del motor NO cambia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Protocol, runtime_checkable


@dataclass
class DeciderResponse:
    """Clasificación de intención devuelta por el modelo (antes de validar).

    Refleja los campos del esquema narrativo. `latency_ms` lo rellena el motor,
    no el backend, por lo que aquí es opcional.
    """

    action_type: str
    target_branch: str
    confidence_score: float
    narrative_response: str
    # El backend puede sugerir el fallback; el motor tiene la última palabra.
    trigger_fallback: bool = False
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        """Convierte la respuesta a un dict acorde al esquema narrativo."""
        return {
            "action_type": self.action_type,
            "target_branch": self.target_branch,
            "confidence_score": self.confidence_score,
            "trigger_fallback": self.trigger_fallback,
            "narrative_response": self.narrative_response,
        }


@runtime_checkable
class DeciderBackend(Protocol):
    """Contrato que debe cumplir cualquier backend de Strands Decider."""

    def classify(self, player_input: str, context: Dict[str, Any]) -> DeciderResponse:
        """Clasifica la intención del jugador y devuelve una `DeciderResponse`."""
        ...


class SimulatedDeciderBackend:
    """Backend determinista basado en reglas (placeholder del modelo real).

    No usa aleatoriedad: para la misma entrada produce siempre la misma salida,
    lo que hace reproducibles las pruebas y la demo. Mapea palabras clave a
    ramas narrativas y asigna un `confidence_score` según la claridad del input.
    Esto NO pretende ser el modelo; es un sustituto honesto hasta conectar
    Strands Decider 2B.
    """

    # Palabras clave -> (action_type, target_branch). Orden = prioridad.
    _INTENT_RULES = [
        (("atacar", "ataca", "golpear", "pelear", "luchar", "attack"),
         ("COMBAT", "branch.combat")),
        (("huir", "escapar", "correr", "flee", "run"),
         ("FLEE", "branch.escape")),
        (("hablar", "preguntar", "decir", "talk", "speak", "ask"),
         ("DIALOGUE", "branch.dialogue")),
        (("explorar", "mirar", "buscar", "investigar", "explore", "search"),
         ("EXPLORE", "branch.exploration")),
        (("usar", "abrir", "coger", "tomar", "use", "open", "take"),
         ("INTERACT", "branch.interaction")),
    ]

    def classify(self, player_input: str, context: Dict[str, Any]) -> DeciderResponse:
        text = (player_input or "").strip().lower()

        if not text:
            # Entrada vacía: intención nula y confianza mínima -> forzará fallback.
            return DeciderResponse(
                action_type="UNKNOWN",
                target_branch="branch.clarify",
                confidence_score=0.0,
                narrative_response="No se percibe ninguna acción clara.",
            )

        tokens = set(text.replace(",", " ").replace(".", " ").split())

        for keywords, (action_type, branch) in self._INTENT_RULES:
            matches = tokens.intersection(keywords)
            if matches:
                # Confianza heurística: una sola palabra clara da alta certeza;
                # mezclas de intenciones la reducen.
                distinct_intents = self._count_distinct_intents(tokens)
                confidence = 0.92 if distinct_intents == 1 else 0.58
                return DeciderResponse(
                    action_type=action_type,
                    target_branch=branch,
                    confidence_score=confidence,
                    narrative_response=(
                        f"El Game Master interpreta la acción como "
                        f"'{action_type}' hacia {branch}."
                    ),
                )

        # Sin coincidencia de intención conocida: confianza baja (triage).
        return DeciderResponse(
            action_type="UNKNOWN",
            target_branch="branch.clarify",
            confidence_score=0.40,
            narrative_response=(
                "La intención del jugador no encaja con ninguna rama conocida."
            ),
        )

    def _count_distinct_intents(self, tokens: set) -> int:
        """Cuenta cuántas intenciones distintas aparecen en el input."""
        found = 0
        for keywords, _ in self._INTENT_RULES:
            if tokens.intersection(keywords):
                found += 1
        return found


class DeciderClient:
    """Fachada estable sobre un `DeciderBackend`.

    El motor de decisión solo depende de esta clase, no del backend concreto.
    """

    def __init__(self, backend: DeciderBackend | None = None) -> None:
        # TODO(integración-real): sustituir el backend simulado por el cliente
        # real de Strands Decider 2B. Debe implementar `DeciderBackend.classify`
        # y respetar el contrato de `DeciderResponse`. No se añade aquí ningún
        # SDK/HTTP porque la arquitectura no especifica el transporte del modelo.
        self._backend: DeciderBackend = backend or SimulatedDeciderBackend()

    def classify(self, player_input: str, context: Dict[str, Any] | None = None) -> DeciderResponse:
        """Enruta el input del jugador por el backend de Strands Decider."""
        return self._backend.classify(player_input, context or {})
