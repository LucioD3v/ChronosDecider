"""
UI / Demo RPG de ChronosDecider.

CLI interactiva en tiempo real: el jugador introduce acciones y ve un panel
con latencia, nivel de certeza y la rama narrativa elegida en cada turno.
"""

from .cli_app import RPGConsoleApp, render_panel

__all__ = ["RPGConsoleApp", "render_panel"]
