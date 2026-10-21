"""
Punto de entrada de ChronosDecider.

Lanza la demo RPG interactiva por consola. Todo el procesamiento se enruta por
el `DecisionEngine`, que usa Strands Decider 2B (adaptador) para clasificar la
intención, valida contra el esquema narrativo y registra telemetría.

Uso:
    python main.py
"""

from __future__ import annotations

from src.ui import RPGConsoleApp


def main() -> None:
    RPGConsoleApp().run()


if __name__ == "__main__":
    main()
