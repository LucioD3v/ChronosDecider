"""
Demo RPG interactiva por consola.

Bucle en tiempo real: lee la acción del jugador, la evalúa con el
`DecisionEngine` y renderiza un panel de métricas (latencia, certeza y rama
narrativa) tras cada turno. Si se dispara el fallback (certeza <= 0.70),
muestra el prompt de aclaración (Human-in-the-Loop).

Solo biblioteca estándar; presentación en texto plano para funcionar en
cualquier terminal (incluida PowerShell en Windows).
"""

from __future__ import annotations

from typing import Optional

from ..config import CONFIDENCE_FALLBACK_THRESHOLD, LATENCY_TARGET_MS
from ..engine import DecisionEngine, EvaluationResult
from ..telemetry import TelemetryPanel, TelemetrySummary

# Comandos de control de la demo (no se envían al motor).
_QUIT_COMMANDS = {"salir", "quit", "exit", ":q"}
_HELP_COMMANDS = {"ayuda", "help", "?"}

_PANEL_WIDTH = 60


def _bar(value: float, width: int = 20) -> str:
    """Dibuja una barra de progreso ASCII para un valor en [0.0, 1.0]."""
    value = max(0.0, min(1.0, value))
    filled = int(round(value * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render_panel(result: EvaluationResult, summary: Optional[TelemetrySummary]) -> str:
    """Construye el panel de métricas en tiempo real como texto.

    Args:
        result: resultado de la última evaluación.
        summary: resumen agregado de telemetría (o `None` si no hay historial).

    Returns:
        El panel completo listo para imprimir.
    """
    line = "=" * _PANEL_WIDTH
    # Marca visual del objetivo de latencia.
    latency_flag = "OK " if result.within_latency_target else "LENTO"
    fallback_flag = "SÍ (Human-in-the-Loop)" if result.trigger_fallback else "no"

    rows = [
        line,
        " PANEL DE TELEMETRÍA EN TIEMPO REAL — ChronosDecider",
        line,
        f" Acción clasificada : {result.action_type}",
        f" Rama narrativa     : {result.target_branch}",
        f" Certeza            : {result.confidence_score:6.1%} {_bar(result.confidence_score)}",
        f" Latencia           : {result.latency_ms:7.2f} ms  (objetivo < {LATENCY_TARGET_MS:.0f} ms) [{latency_flag}]",
        f" Fallback           : {fallback_flag}",
        f" Respuesta GM       : {result.narrative_response}",
    ]

    if summary is not None:
        rows += [
            "-" * _PANEL_WIDTH,
            " HISTORIAL AGREGADO",
            f" Evaluaciones       : {summary.total}",
            f" Latencia media/max : {summary.avg_latency_ms:.2f} / {summary.max_latency_ms:.2f} ms",
            f" Certeza media/últ. : {summary.avg_confidence:.1%} / {summary.last_confidence:.1%}",
            f" Dentro de objetivo : {summary.within_target_ratio:.0%}",
            f" Fallbacks activados: {summary.fallback_count}",
        ]

    rows.append(line)
    return "\n".join(rows)


class RPGConsoleApp:
    """Aplicación de consola que conecta jugador, motor y panel de telemetría."""

    def __init__(self, engine: Optional[DecisionEngine] = None) -> None:
        # El motor crea su propia telemetría si no se le pasa una; aquí
        # reutilizamos la del motor para que el panel y el motor compartan datos.
        self._engine = engine or DecisionEngine()
        self._telemetry: TelemetryPanel = self._engine.telemetry

    def _intro(self) -> None:
        print("=" * _PANEL_WIDTH)
        print(" ChronosDecider — Demo RPG en tiempo real")
        print(" Strands Decider 2B como Game Master ultrarrápido")
        print("=" * _PANEL_WIDTH)
        print(f" Umbral de fallback (Human-in-the-Loop): "
              f"certeza <= {CONFIDENCE_FALLBACK_THRESHOLD:.0%}")
        print(" Escribe una acción (p. ej. 'atacar al goblin', 'explorar la sala').")
        print(f" Comandos: {', '.join(sorted(_HELP_COMMANDS))} | "
              f"{', '.join(sorted(_QUIT_COMMANDS))}")
        print("=" * _PANEL_WIDTH)

    def _help(self) -> None:
        print("\nIntroduce acciones en lenguaje natural. Ejemplos:")
        print("  - atacar al dragón")
        print("  - hablar con el mercader")
        print("  - explorar la cueva")
        print("  - huir del combate")
        print("Las acciones ambiguas activan la aclaración (Human-in-the-Loop).\n")

    def run_turn(self, player_input: str) -> EvaluationResult:
        """Procesa un turno: evalúa la acción y devuelve el resultado.

        Separado del bucle de E/S para poder probarse sin interacción.
        """
        result = self._engine.evaluate(player_input)
        return result

    def run(self) -> None:
        """Bucle interactivo principal de la demo."""
        self._intro()
        while True:
            try:
                player_input = input("\n> acción: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo de ChronosDecider. ¡Hasta la próxima partida!")
                return

            command = player_input.lower()
            if command in _QUIT_COMMANDS:
                print("Saliendo de ChronosDecider. ¡Hasta la próxima partida!")
                return
            if command in _HELP_COMMANDS:
                self._help()
                continue
            if not player_input:
                # Entrada vacía: el motor la clasificará como baja certeza y
                # disparará el fallback; dejamos que fluya para demostrarlo.
                pass

            result = self.run_turn(player_input)
            print()
            print(render_panel(result, self._telemetry.summary()))

            if result.clarification_prompt:
                # Human-in-the-Loop: pedimos aclaración explícita al jugador.
                print(f"\n[ACLARACIÓN] {result.clarification_prompt}")
