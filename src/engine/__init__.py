"""
Decision Engine de ChronosDecider.

Separa la DECISIÓN (Strands Decider 2B) de la GENERACIÓN (Amazon Bedrock):
el Decider elige la rama narrativa con confianza calibrada; el narrador la
redacta. El motor orquesta triage/fallback, validación y telemetría.
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
