"""
ChronosDecider narrator: the GENERATION layer.

Once Strands Decider 2B picks the narrative branch, Amazon Bedrock generates the
Game Master's text for that branch. This is the generative part of the agent
(Decider decides, Bedrock narrates).

Exposes:
  * `Narrator`         : interface (Protocol) of a narrative generator.
  * `BedrockNarrator`  : real generation via boto3 (Amazon Bedrock, us-east-1).
  * `TemplateNarrator` : local template fallback (no credentials, no boto3).
  * `build_default_narrator()` : picks Bedrock if configured, else the template.

boto3 is an OPTIONAL dependency: it is only imported inside `BedrockNarrator`,
so the project runs without installing it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import (
    BEDROCK_MAX_TOKENS,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    NARRATIVE_BRANCHES,
)


@runtime_checkable
class Narrator(Protocol):
    """Contract for a narrative generator."""

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        """Generate the Game Master's narrative text for the chosen branch."""
        ...

    @property
    def source(self) -> str:
        """Identify the narrative's origin ('bedrock' or 'template')."""
        ...


class TemplateNarrator:
    """Local template narrator (fallback without Bedrock).

    Produces a simple but coherent narration so the demo works without AWS
    credentials. It uses no network and no external dependencies.
    """

    @property
    def source(self) -> str:
        return "template"

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        description = NARRATIVE_BRANCHES.get(branch_id, ("", "an unexpected action"))[1]
        action = player_input.strip() or "something uncertain"
        return (
            f"The Game Master resolves the '{branch_id}' branch ({action_type}). "
            f"{description} Faced with \u00ab{action}\u00bb, the scene moves forward "
            f"and the world reacts."
        )


class BedrockNarrator:
    """Real generative narrator with Amazon Bedrock (boto3).

    Uses the bedrock-runtime Converse API, common to Bedrock chat models.
    `boto3` is imported here so it stays an optional dependency.
    """

    def __init__(
        self,
        model_id: str = BEDROCK_MODEL_ID,
        region: str = BEDROCK_REGION,
        max_tokens: int = BEDROCK_MAX_TOKENS,
    ) -> None:
        if not model_id:
            raise ValueError(
                "BEDROCK_MODEL_ID is empty: set CHRONOS_BEDROCK_MODEL_ID to the "
                "id of a model enabled in Bedrock (Model access)."
            )
        import boto3  # Local import: optional dependency.

        self._model_id = model_id
        self._max_tokens = max_tokens
        self._client = boto3.client("bedrock-runtime", region_name=region)

    @property
    def source(self) -> str:
        return "bedrock"

    def _build_prompt(self, player_input: str, branch_id: str, action_type: str) -> str:
        description = NARRATIVE_BRANCHES.get(branch_id, ("", ""))[1]
        return (
            "You are the Game Master of a real-time RPG. The narrative branch has "
            "already been decided; your only task is to narrate it in 2-3 "
            "sentences, in the second person, without offering options or lists.\n"
            f"Player action: {player_input!r}\n"
            f"Chosen branch: {branch_id} ({action_type}). {description}\n"
            "Narrate the immediate outcome of that action:"
        )

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        prompt = self._build_prompt(player_input, branch_id, action_type)
        response = self._client.converse(
            modelId=self._model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.7},
        )
        # Standard Converse response structure.
        content = response["output"]["message"]["content"]
        text = "".join(part.get("text", "") for part in content).strip()
        return text or "(the Game Master stays silent)"


def build_default_narrator() -> Narrator:
    """Pick the narrator based on the available configuration.

    - If `BEDROCK_MODEL_ID` is set and `boto3` can be initialized, use
      `BedrockNarrator`.
    - In any other case, fall back to the local `TemplateNarrator`, so the agent
      keeps working without credentials.
    """
    if BEDROCK_MODEL_ID:
        try:
            return BedrockNarrator()
        except Exception:
            # boto3 missing, credentials misconfigured, etc.: degrade without breaking.
            return TemplateNarrator()
    return TemplateNarrator()
