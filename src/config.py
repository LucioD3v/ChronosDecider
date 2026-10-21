"""
Configuración central de ChronosDecider.

Combina las reglas de la arquitectura (`.kiro/steer/system_architecture.md`) con
la integración real: Strands Decider 2B (decisión) y Amazon Bedrock (generación).
Los valores sensibles al entorno se leen de variables de entorno, con valores por
defecto razonables para desarrollo local.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Rutas del proyecto -----------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# Esquema JSON que valida TODA salida del motor (regla 2 de la arquitectura).
NARRATIVE_SCHEMA_PATH: Path = PROJECT_ROOT / ".kiro" / "steer" / "narrative_schema.json"

# --- Reglas del motor (ver system_architecture.md) --------------------------
# Objetivo de latencia de la DECISIÓN, en milisegundos.
LATENCY_TARGET_MS: float = 100.0

# Umbral de triage/Human-in-the-Loop:
# si confidence_score <= este valor se activa el fallback (regla 3).
CONFIDENCE_FALLBACK_THRESHOLD: float = 0.70

# --- Catálogo de ramas narrativas (opciones de la decisión "choice") --------
# Cada entrada: id de rama -> (action_type, descripción corta para el narrador).
# El conjunto de opciones se le pasa a Strands Decider como la pregunta tipada.
NARRATIVE_BRANCHES: dict[str, tuple[str, str]] = {
    "combat": ("COMBAT", "El jugador entra en combate."),
    "dialogue": ("DIALOGUE", "El jugador conversa con un personaje."),
    "exploration": ("EXPLORE", "El jugador explora o investiga el entorno."),
    "flee": ("FLEE", "El jugador huye o evita el peligro."),
    "interaction": ("INTERACT", "El jugador usa o manipula un objeto."),
}

# Rama especial para cuando la decisión no es fiable (fallback).
CLARIFY_BRANCH_ID: str = "clarify"

# --- Strands Decider 2B (servidor local open source) ------------------------
# El modelo se sirve con: `strands-decider serve <modelo> --port 8000`.
DECIDER_SERVER_URL: str = os.environ.get("CHRONOS_DECIDER_URL", "http://localhost:8000")
DECIDER_SYSTEMONE_PATH: str = "/v1/systemone"
DECIDER_MODEL_ID: str = os.environ.get(
    "CHRONOS_DECIDER_MODEL", "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
)
# Tiempo máximo de espera (s) para la llamada HTTP al servidor del modelo.
DECIDER_TIMEOUT_S: float = float(os.environ.get("CHRONOS_DECIDER_TIMEOUT", "5.0"))

# --- Amazon Bedrock (generación de narrativa) -------------------------------
BEDROCK_REGION: str = os.environ.get("CHRONOS_BEDROCK_REGION", "us-east-1")
# Id del modelo generativo habilitado en tu cuenta (Model access en la consola).
# Vacío por defecto: sin configurar, el motor usa el narrador de plantilla local.
BEDROCK_MODEL_ID: str = os.environ.get("CHRONOS_BEDROCK_MODEL_ID", "")
BEDROCK_MAX_TOKENS: int = int(os.environ.get("CHRONOS_BEDROCK_MAX_TOKENS", "256"))
