"""
Central configuration for ChronosDecider.

Combines the architecture rules (`.kiro/steer/system_architecture.md`) with the
real integration: Strands Decider 2B (decision) and Amazon Bedrock (generation).
Environment-sensitive values are read from environment variables, with sensible
defaults for local development.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Project paths ----------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

# JSON schema that validates ALL engine output (rule 2 of the architecture).
NARRATIVE_SCHEMA_PATH: Path = PROJECT_ROOT / ".kiro" / "steer" / "narrative_schema.json"

# --- Engine rules (see system_architecture.md) ------------------------------
# Target latency for the DECISION, in milliseconds.
LATENCY_TARGET_MS: float = 100.0

# Triage / Human-in-the-Loop threshold:
# if confidence_score <= this value, the fallback is triggered (rule 3).
CONFIDENCE_FALLBACK_THRESHOLD: float = 0.70

# --- Narrative branch catalog (options for the "choice" decision) -----------
# Each entry: branch id -> (action_type, short description for the narrator).
# The option set is passed to Strands Decider as the typed question.
NARRATIVE_BRANCHES: dict[str, tuple[str, str]] = {
    "combat": ("COMBAT", "The player enters combat."),
    "dialogue": ("DIALOGUE", "The player talks to a character."),
    "exploration": ("EXPLORE", "The player explores or investigates the surroundings."),
    "flee": ("FLEE", "The player flees or avoids danger."),
    "interaction": ("INTERACT", "The player uses or manipulates an object."),
}

# Special branch for when the decision is not reliable (fallback).
CLARIFY_BRANCH_ID: str = "clarify"

# --- Strands Decider 2B (local open-source server) --------------------------
# The model is served with: `strands-decider serve <model> --port 8000`.
DECIDER_SERVER_URL: str = os.environ.get("CHRONOS_DECIDER_URL", "http://localhost:8000")
DECIDER_SYSTEMONE_PATH: str = "/v1/systemone"
DECIDER_MODEL_ID: str = os.environ.get(
    "CHRONOS_DECIDER_MODEL", "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
)
# Maximum wait time (s) for the HTTP call to the model server.
DECIDER_TIMEOUT_S: float = float(os.environ.get("CHRONOS_DECIDER_TIMEOUT", "5.0"))

# --- Amazon Bedrock (narrative generation) ----------------------------------
BEDROCK_REGION: str = os.environ.get("CHRONOS_BEDROCK_REGION", "us-east-1")
# Id of the generative model enabled in your account (Model access in the console).
# Empty by default: when unset, the engine uses the local template narrator.
BEDROCK_MODEL_ID: str = os.environ.get("CHRONOS_BEDROCK_MODEL_ID", "")
BEDROCK_MAX_TOKENS: int = int(os.environ.get("CHRONOS_BEDROCK_MAX_TOKENS", "256"))
