"""
Patrón de decisión reutilizable: TOOL SELECTION con Strands Decider 2B.

Problema que resuelve
---------------------
Un agente recibe texto del usuario y tiene varias herramientas (o ramas) entre
las que elegir. Dejar que un LLM decida por generación es lento, caro y propenso
a elegir con exceso de confianza. Strands Decider 2B responde una pregunta
`choice` tipada con una confianza CALIBRADA, en una sola pasada, para que el
agente actúe solo cuando la decisión es fiable y pida ayuda cuando no lo es.

Este módulo es independiente de ChronosDecider: no importa nada del paquete
`src`. Cualquiera puede copiar `decision_patterns/` a su proyecto y usarlo.

Qué incluye (los tres elementos que pide la hackathon)
------------------------------------------------------
1. La pregunta tipada y el conjunto de opciones -> `build_choice_question`.
2. El wiring que lo pone en la ruta del agente -> `ToolSelectionPattern.select`,
   pensado para un gate tipo `before_tool_call` / InterventionHandler.
3. Nota de uso -> README.md de esta carpeta y los docstrings de aquí.

Transporte
----------
Habla con el servidor de Strands Decider (`strands-decider serve ... --port 8000`)
vía el endpoint `/v1/systemone`, usando solo la biblioteca estándar (`urllib`).
No añade dependencias.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_MODEL_ID = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
_SYSTEMONE_PATH = "/v1/systemone"
_QUESTION_NAME = "tool_choice"


@dataclass
class ToolChoice:
    """Resultado de una decisión de selección de herramienta.

    Attributes:
        tool: la opción elegida (una de las que se pasaron), o None si el modelo
            devolvió algo fuera del conjunto.
        confidence: confianza calibrada [0.0, 1.0] de la elección.
        should_act: True si `confidence > threshold`; si es False, el agente debe
            pedir aclaración en vez de ejecutar la herramienta (guardrail).
        latency_ms: latencia de ida y vuelta medida localmente.
        raw: respuesta cruda del servidor para depuración.
    """

    tool: Optional[str]
    confidence: float
    should_act: bool
    latency_ms: float
    raw: Dict[str, Any] = field(default_factory=dict)


def build_choice_question(instructions: str, options: List[str]) -> Dict[str, Any]:
    """Construye el cuerpo `/v1/systemone` para una pregunta `choice`.

    Args:
        instructions: la pregunta en lenguaje natural (p. ej. "¿Qué herramienta
            debe usar el agente?").
        options: lista de etiquetas de opción (los nombres de tus herramientas).

    Returns:
        El dict listo para serializar como JSON y enviar al servidor.

    El servidor espera las opciones embebidas en `instructions` con el formato
    `pregunta=opt1,opt2,...`, idéntico al del CLI `--choice`.
    """
    if not options:
        raise ValueError("Se requiere al menos una opción para la pregunta choice.")
    return {
        "state": "",  # se rellena en tiempo de llamada
        "questions": {
            _QUESTION_NAME: {
                "type": "choice",
                "instructions": f"{instructions}={','.join(options)}",
            }
        },
    }


def parse_choice_answer(
    payload: Dict[str, Any], options: List[str], threshold: float, latency_ms: float
) -> ToolChoice:
    """Traduce la respuesta del servidor a un `ToolChoice`.

    Es tolerante con variaciones de forma: acepta `choice`, `value` o una
    distribución `probabilities` (en cuyo caso toma el argmax).
    """
    answer = payload.get("answers", {}).get(_QUESTION_NAME, {})
    tool = answer.get("choice") or answer.get("value")
    confidence = answer.get("confidence")

    if tool is None and isinstance(answer.get("probabilities"), dict):
        probs: Dict[str, float] = answer["probabilities"]
        tool = max(probs, key=probs.get)
        confidence = probs[tool]

    conf = float(confidence) if confidence is not None else 0.0
    if tool not in options:
        # Elección fuera del conjunto: trátala como no fiable.
        return ToolChoice(tool=None, confidence=conf, should_act=False,
                          latency_ms=latency_ms, raw=payload)

    return ToolChoice(tool=tool, confidence=conf, should_act=conf > threshold,
                      latency_ms=latency_ms, raw=payload)


class ToolSelectionPattern:
    """Selector de herramienta reutilizable respaldado por Strands Decider 2B.

    Uso típico (gate antes de ejecutar una herramienta):

        pattern = ToolSelectionPattern(
            instructions="¿Qué herramienta responde mejor al usuario?",
            options=["buscar_web", "consultar_db", "responder_directo"],
            confidence_threshold=0.70,
        )
        choice = pattern.select(user_input)
        if choice.should_act:
            ejecutar_herramienta(choice.tool)
        else:
            pedir_aclaracion_al_usuario()
    """

    def __init__(
        self,
        instructions: str,
        options: List[str],
        confidence_threshold: float = 0.70,
        server_url: str = DEFAULT_SERVER_URL,
        model_id: str = DEFAULT_MODEL_ID,
        timeout_s: float = 5.0,
    ) -> None:
        self.instructions = instructions
        self.options = list(options)
        self.confidence_threshold = confidence_threshold
        self._url = server_url.rstrip("/") + _SYSTEMONE_PATH
        self._model_id = model_id
        self._timeout_s = timeout_s

    def select(self, state: str) -> ToolChoice:
        """Pregunta a Decider qué herramienta usar para `state` (texto del usuario)."""
        body = build_choice_question(self.instructions, self.options)
        body["state"] = state
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - start) * 1000.0
        return parse_choice_answer(payload, self.options, self.confidence_threshold, latency_ms)

    def as_intervention(
        self, execute: Callable[[str], Any], on_low_confidence: Callable[[ToolChoice], Any]
    ) -> Callable[[str], Any]:
        """Envuelve el patrón como un gate estilo `before_tool_call`.

        Devuelve una función `handler(state)` que ejecuta la herramienta elegida
        solo si la confianza supera el umbral; si no, invoca `on_low_confidence`
        para que el agente pida aclaración (patrón guardrail).
        """
        def handler(state: str) -> Any:
            choice = self.select(state)
            if choice.should_act and choice.tool is not None:
                return execute(choice.tool)
            return on_low_confidence(choice)

        return handler
