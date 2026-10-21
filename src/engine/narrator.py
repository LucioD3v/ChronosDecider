"""
Narrador de ChronosDecider: la capa de GENERACIÓN.

Una vez que Strands Decider 2B decide la rama narrativa, Amazon Bedrock genera el
texto del Game Master para esa rama. Esta es la parte generativa del agente
(Decider decide, Bedrock narra).

Expone:
  * `Narrator`         : interfaz (Protocol) de un generador de narrativa.
  * `BedrockNarrator`  : generación real vía boto3 (Amazon Bedrock, us-east-1).
  * `TemplateNarrator` : fallback local de plantilla (sin credenciales ni boto3).
  * `build_default_narrator()` : elige Bedrock si está configurado, si no plantilla.

boto3 es una dependencia OPCIONAL: solo se importa dentro de `BedrockNarrator`,
para que el proyecto corra sin instalarla.
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
    """Contrato de un generador de narrativa."""

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        """Genera el texto narrativo del Game Master para la rama elegida."""
        ...

    @property
    def source(self) -> str:
        """Identifica el origen de la narrativa ('bedrock' o 'template')."""
        ...


class TemplateNarrator:
    """Narrador local de plantilla (fallback sin Bedrock).

    Produce una narración simple pero coherente para que la demo funcione sin
    credenciales de AWS. No usa red ni dependencias externas.
    """

    @property
    def source(self) -> str:
        return "template"

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        descripcion = NARRATIVE_BRANCHES.get(branch_id, ("", "una acción inesperada"))[1]
        accion = player_input.strip() or "algo incierto"
        return (
            f"El Game Master resuelve la rama '{branch_id}' ({action_type}). "
            f"{descripcion} Ante «{accion}», la escena avanza y el mundo reacciona."
        )


class BedrockNarrator:
    """Narrador generativo real con Amazon Bedrock (boto3).

    Usa la API Converse de bedrock-runtime, común a los modelos de chat de Bedrock.
    `boto3` se importa aquí para que sea una dependencia opcional.
    """

    def __init__(
        self,
        model_id: str = BEDROCK_MODEL_ID,
        region: str = BEDROCK_REGION,
        max_tokens: int = BEDROCK_MAX_TOKENS,
    ) -> None:
        if not model_id:
            raise ValueError(
                "BEDROCK_MODEL_ID vacío: configura CHRONOS_BEDROCK_MODEL_ID con el "
                "id de un modelo habilitado en Bedrock (Model access)."
            )
        import boto3  # Import local: dependencia opcional.

        self._model_id = model_id
        self._max_tokens = max_tokens
        self._client = boto3.client("bedrock-runtime", region_name=region)

    @property
    def source(self) -> str:
        return "bedrock"

    def _build_prompt(self, player_input: str, branch_id: str, action_type: str) -> str:
        descripcion = NARRATIVE_BRANCHES.get(branch_id, ("", ""))[1]
        return (
            "Eres el Game Master de un RPG en tiempo real. La decisión de la rama "
            "narrativa ya está tomada; tu única tarea es narrarla en 2-3 frases, "
            "en segunda persona y en español, sin ofrecer opciones ni listas.\n"
            f"Acción del jugador: {player_input!r}\n"
            f"Rama elegida: {branch_id} ({action_type}). {descripcion}\n"
            "Narra el desenlace inmediato de esa acción:"
        )

    def narrate(self, player_input: str, branch_id: str, action_type: str) -> str:
        prompt = self._build_prompt(player_input, branch_id, action_type)
        response = self._client.converse(
            modelId=self._model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": self._max_tokens, "temperature": 0.7},
        )
        # Estructura estándar de la respuesta Converse.
        content = response["output"]["message"]["content"]
        text = "".join(part.get("text", "") for part in content).strip()
        return text or "(el Game Master guarda silencio)"


def build_default_narrator() -> Narrator:
    """Elige el narrador según la configuración disponible.

    - Si `BEDROCK_MODEL_ID` está configurado e `boto3` puede inicializarse, usa
      `BedrockNarrator`.
    - En cualquier otro caso, cae al `TemplateNarrator` local, para que el agente
      siga funcionando sin credenciales.
    """
    if BEDROCK_MODEL_ID:
        try:
            return BedrockNarrator()
        except Exception:
            # boto3 ausente, credenciales mal configuradas, etc.: degradar sin romper.
            return TemplateNarrator()
    return TemplateNarrator()
