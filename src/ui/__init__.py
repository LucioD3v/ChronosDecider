"""
ChronosDecider UI / RPG demo.

Real-time interactive CLI: the player enters actions and sees a panel with the
latency, confidence level and chosen narrative branch on each turn.
"""

from .cli_app import RPGConsoleApp, render_panel

__all__ = ["RPGConsoleApp", "render_panel"]
