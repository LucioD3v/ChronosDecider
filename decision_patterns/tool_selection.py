"""
Reusable decision pattern: TOOL SELECTION with Strands Decider 2B.

Problem it solves
-----------------
An agent receives user text and has several tools (or branches) to choose from.
Letting an LLM decide via generation is slow, expensive and prone to choosing
with overconfidence. Strands Decider 2B answers a typed `choice` question with a
CALIBRATED confidence, in a single pass, so the agent acts only when the
decision is reliable and asks for help when it is not.

This module is independent of ChronosDecider: it imports nothing from the `src`
package. Anyone can copy `decision_patterns/` into their project and use it.

What it includes (the three elements the hackathon asks for)
------------------------------------------------------------
1. The typed question and option set -> `build_choice_question`.
2. The wiring that puts it in the agent's path -> `ToolSelectionPattern.select`,
   designed for a `before_tool_call` / InterventionHandler-style gate.
3. Usage note -> this folder's README.md and the docstrings here.

Transport
---------
Talks to the Strands Decider server (`strands-decider serve ... --port 8000`)
via the `/v1/systemone` endpoint, using only the standard library (`urllib`).
It adds no dependencies.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_MODEL_ID = "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610"
_SYSTEMONE_PATH = "/v1/systemone"
_QUESTION_NAME = "tool_choice"


@dataclass
class ToolChoice:
    """Result of a tool-selection decision.

    Attributes:
        tool: the chosen option (one of those passed in), or None if the model
            returned something outside the set.
        confidence: calibrated confidence [0.0, 1.0] of the choice.
        should_act: True if `confidence > threshold`; if False, the agent should
            ask for clarification instead of running the tool (guardrail).
        latency_ms: round-trip latency measured locally.
        raw: raw server response for debugging.
    """

    tool: Optional[str]
    confidence: float
    should_act: bool
    latency_ms: float
    raw: Dict[str, Any] = field(default_factory=dict)


def build_choice_question(instructions: str, options: List[str]) -> Dict[str, Any]:
    """Build the `/v1/systemone` body for a `choice` question.

    Args:
        instructions: the natural-language question (e.g. "Which tool should the
            agent use?").
        options: list of option labels (the names of your tools).

    Returns:
        The dict ready to serialize as JSON and send to the server.

    The server expects the options embedded in `instructions` using the
    `question=opt1,opt2,...` format, identical to the CLI's `--choice`.
    """
    if not options:
        raise ValueError("At least one option is required for the choice question.")
    return {
        "state": "",  # filled in at call time
        "questions": {
            _QUESTION_NAME: {
                "type": "choice",
                "instructions": f"{instructions}={','.join(options)}",
            }
        },
    }


def parse_choice_answer(
    payload: Dict[str, Any], options: List[str], threshold: float, latency_ms: float
) -> ToolChoice:
    """Translate the server response into a `ToolChoice`.

    It tolerates shape variations: it accepts `choice`, `value` or a
    `probabilities` distribution (in which case it takes the argmax).
    """
    answer = payload.get("answers", {}).get(_QUESTION_NAME, {})
    tool = answer.get("choice") or answer.get("value")
    confidence = answer.get("confidence")

    if tool is None and isinstance(answer.get("probabilities"), dict):
        probs: Dict[str, float] = answer["probabilities"]
        tool = max(probs, key=probs.get)
        confidence = probs[tool]

    conf = float(confidence) if confidence is not None else 0.0
    if tool not in options:
        # Choice outside the set: treat it as not reliable.
        return ToolChoice(tool=None, confidence=conf, should_act=False,
                          latency_ms=latency_ms, raw=payload)

    return ToolChoice(tool=tool, confidence=conf, should_act=conf > threshold,
                      latency_ms=latency_ms, raw=payload)


class ToolSelectionPattern:
    """Reusable tool selector backed by Strands Decider 2B.

    Typical usage (gate before running a tool):

        pattern = ToolSelectionPattern(
            instructions="Which tool best answers the user?",
            options=["web_search", "query_db", "answer_directly"],
            confidence_threshold=0.70,
        )
        choice = pattern.select(user_input)
        if choice.should_act:
            run_tool(choice.tool)
        else:
            ask_user_for_clarification()
    """

    def __init__(
        self,
        instructions: str,
        options: List[str],
        confidence_threshold: float = 0.70,
        server_url: str = DEFAULT_SERVER_URL,
        model_id: str = DEFAULT_MODEL_ID,
        timeout_s: float = 5.0,
    ) -> None:
        self.instructions = instructions
        self.options = list(options)
        self.confidence_threshold = confidence_threshold
        self._url = server_url.rstrip("/") + _SYSTEMONE_PATH
        self._model_id = model_id
        self._timeout_s = timeout_s

    def select(self, state: str) -> ToolChoice:
        """Ask Decider which tool to use for `state` (the user's text)."""
        body = build_choice_question(self.instructions, self.options)
        body["state"] = state
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self._url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - start) * 1000.0
        return parse_choice_answer(payload, self.options, self.confidence_threshold, latency_ms)

    def as_intervention(
        self, execute: Callable[[str], Any], on_low_confidence: Callable[[ToolChoice], Any]
    ) -> Callable[[str], Any]:
        """Wrap the pattern as a `before_tool_call`-style gate.

        Returns a `handler(state)` function that runs the chosen tool only if the
        confidence clears the threshold; otherwise it invokes `on_low_confidence`
        so the agent asks for clarification (guardrail pattern).
        """
        def handler(state: str) -> Any:
            choice = self.select(state)
            if choice.should_act and choice.tool is not None:
                return execute(choice.tool)
            return on_low_confidence(choice)

        return handler
