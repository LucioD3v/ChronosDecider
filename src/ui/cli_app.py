"""
Interactive console RPG demo.

Real-time loop: read the player's action, evaluate it with the `DecisionEngine`
and render a metrics panel (latency, confidence and narrative branch) after each
turn. If the fallback triggers (confidence <= 0.70), it shows the clarification
prompt (Human-in-the-Loop).

Standard library only; plain-text presentation so it works in any terminal
(including PowerShell on Windows).
"""

from __future__ import annotations

from typing import Optional

from ..config import CONFIDENCE_FALLBACK_THRESHOLD, LATENCY_TARGET_MS
from ..engine import DecisionEngine, EvaluationResult
from ..telemetry import TelemetryPanel, TelemetrySummary

# Demo control commands (not sent to the engine). English and Spanish aliases.
_QUIT_COMMANDS = {"quit", "exit", "salir", ":q"}
_HELP_COMMANDS = {"help", "ayuda", "?"}
_EXPORT_COMMANDS = {"export", "exportar", ":e"}

_PANEL_WIDTH = 60


def _bar(value: float, width: int = 20) -> str:
    """Draw an ASCII progress bar for a value in [0.0, 1.0]."""
    value = max(0.0, min(1.0, value))
    filled = int(round(value * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def render_panel(result: EvaluationResult, summary: Optional[TelemetrySummary]) -> str:
    """Build the real-time metrics panel as text.

    Args:
        result: result of the last evaluation.
        summary: aggregated telemetry summary (or `None` if no history).

    Returns:
        The full panel ready to print.
    """
    line = "=" * _PANEL_WIDTH
    # Visual marker for the latency target.
    latency_flag = "OK " if result.within_latency_target else "SLOW"
    fallback_flag = "YES (Human-in-the-Loop)" if result.trigger_fallback else "no"

    rows = [
        line,
        " REAL-TIME TELEMETRY PANEL \u2014 ChronosDecider",
        line,
        f" Classified action : {result.action_type}",
        f" Narrative branch  : {result.target_branch}",
        f" Confidence        : {result.confidence_score:6.1%} {_bar(result.confidence_score)}",
        f" Decision latency  : {result.decision_latency_ms:7.2f} ms  (target < {LATENCY_TARGET_MS:.0f} ms) [{latency_flag}]",
        f" Decision via      : {result.decision_source}",
        f" Narrative via     : {result.narrative_source}",
        f" Fallback          : {fallback_flag}",
        f" GM response       : {result.narrative_response or '(not narrated: clarification requested)'}",
    ]

    if summary is not None:
        rows += [
            "-" * _PANEL_WIDTH,
            " AGGREGATED HISTORY",
            f" Evaluations       : {summary.total}",
            f" Latency avg/max   : {summary.avg_latency_ms:.2f} / {summary.max_latency_ms:.2f} ms",
            f" Confidence avg/last: {summary.avg_confidence:.1%} / {summary.last_confidence:.1%}",
            f" Within target     : {summary.within_target_ratio:.0%}",
            f" Fallbacks fired   : {summary.fallback_count}",
        ]

    rows.append(line)
    return "\n".join(rows)


class RPGConsoleApp:
    """Console app wiring together player, engine and telemetry panel."""

    def __init__(self, engine: Optional[DecisionEngine] = None) -> None:
        # The engine creates its own telemetry if none is passed; here we reuse
        # the engine's so the panel and the engine share the same data.
        self._engine = engine or DecisionEngine()
        self._telemetry: TelemetryPanel = self._engine.telemetry

    def _intro(self) -> None:
        print("=" * _PANEL_WIDTH)
        print(" ChronosDecider \u2014 Real-time RPG demo")
        print(" Strands Decider 2B as an ultra-fast Game Master")
        print("=" * _PANEL_WIDTH)
        print(f" Fallback threshold (Human-in-the-Loop): "
              f"confidence <= {CONFIDENCE_FALLBACK_THRESHOLD:.0%}")
        print(" Type an action (e.g. 'attack the goblin', 'explore the room').")
        print(f" Commands: {', '.join(sorted(_HELP_COMMANDS))} | "
              f"{', '.join(sorted(_EXPORT_COMMANDS))} | "
              f"{', '.join(sorted(_QUIT_COMMANDS))}")
        print("=" * _PANEL_WIDTH)

    def _help(self) -> None:
        print("\nEnter actions in natural language. Examples:")
        print("  - attack the dragon")
        print("  - talk to the merchant")
        print("  - explore the cave")
        print("  - flee from combat")
        print("Ambiguous actions trigger clarification (Human-in-the-Loop).")
        print("Type 'export' to save the session metrics as JSON.\n")

    def _export(self) -> None:
        """Export the current session's telemetry to a JSON file."""
        if self._telemetry.summary() is None:
            print("\n[EXPORT] No metrics to export yet. "
                  "Play at least one turn first.\n")
            return
        try:
            path = self._telemetry.export_json()
        except OSError as exc:
            print(f"\n[EXPORT] Could not write the file: {exc}\n")
            return
        print(f"\n[EXPORT] Session metrics saved to: {path.resolve()}\n")

    def run_turn(self, player_input: str) -> EvaluationResult:
        """Process a turn: evaluate the action and return the result.

        Separated from the I/O loop so it can be tested without interaction.
        """
        result = self._engine.evaluate(player_input)
        return result

    def run(self) -> None:
        """Main interactive loop of the demo."""
        self._intro()
        while True:
            try:
                player_input = input("\n> action: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting ChronosDecider. See you next game!")
                return

            command = player_input.lower()
            if command in _QUIT_COMMANDS:
                print("Exiting ChronosDecider. See you next game!")
                return
            if command in _HELP_COMMANDS:
                self._help()
                continue
            if command in _EXPORT_COMMANDS:
                self._export()
                continue
            if not player_input:
                # Empty input: the engine classifies it as low confidence and
                # triggers the fallback; we let it flow to demonstrate it.
                pass

            result = self.run_turn(player_input)
            print()
            print(render_panel(result, self._telemetry.summary()))

            if result.clarification_prompt:
                # Human-in-the-Loop: we ask the player for an explicit clarification.
                print(f"\n[CLARIFICATION] {result.clarification_prompt}")
