"""
Ejemplo mínimo del patrón Tool Selection contra un servidor Strands Decider local.

Ejecuta:
    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000
y luego:
    python decision_patterns/example.py
"""

from __future__ import annotations

import urllib.error

from decision_patterns import ToolSelectionPattern


def main() -> None:
    pattern = ToolSelectionPattern(
        instructions="¿Qué equipo debe atender este mensaje?",
        options=["billing", "sales", "retail"],
        confidence_threshold=0.70,
    )

    mensaje = "¡Ayuda! Mis pagos llevan 3 días fallando."
    try:
        choice = pattern.select(mensaje)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        print("No se pudo contactar al servidor de Strands Decider en "
              f"{pattern._url!r}: {exc}")
        print("Levántalo con:")
        print("  strands-decider serve "
              "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000")
        return

    print(f"Mensaje     : {mensaje}")
    print(f"Elección    : {choice.tool}")
    print(f"Confianza   : {choice.confidence:.3f}")
    print(f"¿Actuar?    : {choice.should_act} (umbral {pattern.confidence_threshold})")
    print(f"Latencia    : {choice.latency_ms:.1f} ms")
    if not choice.should_act:
        print("Guardrail   : confianza insuficiente -> pedir aclaración antes de actuar.")


if __name__ == "__main__":
    main()
