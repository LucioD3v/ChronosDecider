"""
ChronosDecider Decision Engine.

Separates the DECISION (Strands Decider 2B) from the GENERATION (Amazon Bedrock):
the Decider picks the narrative branch with calibrated confidence; the narrator
writes it. The engine orchestrates triage/fallback, validation and telemetry.
"""

from .decider_client import (
    DeciderBackend,
    DeciderClient,
    DecisionResult,
    SimulatedDeciderBackend,
    StrandsDeciderHTTPBackend,
)
from .narrator import (
    BedrockNarrator,
    Narrator,
    TemplateNarrator,
    build_default_narrator,
)
from .schema_validator import SchemaValidationError, validate_narrative_output
from .decision_engine import DecisionEngine, EvaluationResult

__all__ = [
    "DeciderBackend",
    "DeciderClient",
    "DecisionResult",
    "SimulatedDeciderBackend",
    "StrandsDeciderHTTPBackend",
    "BedrockNarrator",
    "Narrator",
    "TemplateNarrator",
    "build_default_narrator",
    "SchemaValidationError",
    "validate_narrative_output",
    "DecisionEngine",
    "EvaluationResult",
]
