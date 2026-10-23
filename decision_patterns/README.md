# Reusable decision pattern: Tool Selection

> Tags: `#strands-decider-2b` `#tool-selection`

A recipe any builder can drop into their own agent so that **Strands Decider 2B**
chooses which tool (or branch) to run from the user's text, with a **calibrated
confidence** that doubles as a guardrail: if the decision is not reliable, the
agent asks for clarification instead of acting blindly.

It is independent of the rest of the project: copy the `decision_patterns/`
folder into your repo and use it. It uses only the Python standard library
(`urllib`).

## The three elements of the pattern

**1. The typed question and option set**

A Decider `choice` question: natural-language instructions and your tool labels
as options.

```python
from decision_patterns import ToolSelectionPattern

pattern = ToolSelectionPattern(
    instructions="Which tool best answers the user?",
    options=["web_search", "query_db", "answer_directly"],
    confidence_threshold=0.70,
)
```

**2. The wiring in the agent's path** (a `before_tool_call`-style gate)

```python
choice = pattern.select(user_input)
if choice.should_act:
    result = run_tool(choice.tool)        # confidence > threshold
else:
    ask_user_for_clarification(choice)    # guardrail: do not act blindly
```

Or as a wrapped handler, ready for a Strands Agents InterventionHandler:

```python
handler = pattern.as_intervention(
    execute=lambda tool: run_tool(tool),
    on_low_confidence=lambda ch: ask_user_for_clarification(ch),
)
handler(user_input)
```

**3. Usage note**

- Start the model server:
  `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000`
- The options you pass in `options` are the exact labels Decider can return. Keep
  them short and distinct from each other.
- `confidence_threshold` controls the guardrail. Decider's confidence is
  calibrated: above ~0.9 it is right the vast majority of the time; below that,
  confirm with a person. Tune the threshold to your risk tolerance.
- `select()` also returns `latency_ms`, useful to measure the savings versus
  asking a generative LLM for the decision.

## How ChronosDecider uses it

ChronosDecider applies exactly this pattern: the player's action is the `state`,
and the options are the narrative branches (`combat`, `dialogue`, `exploration`,
`flee`, `interaction`). If confidence clears the threshold, Amazon Bedrock
narrates the branch; otherwise the Game Master asks for clarification. See
`src/engine/decider_client.py`.

## Runnable example

`example.py` in this folder shows the pattern against a local server. If the
server is not running, it explains how to start it.
