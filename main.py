"""
ChronosDecider entry point.

Launches the interactive console RPG demo. All processing is routed through the
`DecisionEngine`, which uses Strands Decider 2B to make the decision, validates
against the narrative schema and records telemetry.

Usage:
    python main.py
"""

from __future__ import annotations

from src.ui import RPGConsoleApp


def main() -> None:
    RPGConsoleApp().run()


if __name__ == "__main__":
    main()
