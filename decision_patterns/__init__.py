"""
Patrones de decisión reutilizables para Strands Decider 2B.

Entregable de la Agent Experience Hackathon: recetas de decisión que otro
builder puede soltar en su propio agente. Ver README.md de esta carpeta.
"""

from .tool_selection import (
    ToolChoice,
    ToolSelectionPattern,
    build_choice_question,
    parse_choice_answer,
)

__all__ = [
    "ToolChoice",
    "ToolSelectionPattern",
    "build_choice_question",
    "parse_choice_answer",
]
