"""
Configuración central de ChronosDecider.

Todos los valores aquí derivan directamente de la arquitectura definida en
`.kiro/steer/system_architecture.md`. No se añaden parámetros no especificados.
"""

from __future__ import annotations

from pathlib import Path

# --- Rutas del proyecto -----------------------------------------------------
# Raíz del repositorio (dos niveles por encima de este archivo: src/ -> raíz).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# Esquema JSON que valida TODA salida del modelo (regla 2 de la arquitectura).
NARRATIVE_SCHEMA_PATH: Path = PROJECT_ROOT / ".kiro" / "steer" / "narrative_schema.json"

# --- Reglas del motor (ver system_architecture.md) --------------------------
# Objetivo de latencia por evaluación, en milisegundos.
LATENCY_TARGET_MS: float = 100.0

# Umbral de triage/Human-in-the-Loop:
# si confidence_score <= este valor se activa el fallback (regla 3).
CONFIDENCE_FALLBACK_THRESHOLD: float = 0.70
