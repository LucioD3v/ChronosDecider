# Demo video script (< 3 minutes)

> Judges' goal: see the agent working and, above all, see the Decider 2B decision
> in action. Keep it under 3:00. Record at 1080p.

## Pre-recording checklist

- [ ] Decider server running: `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000`
- [ ] (Optional but recommended) Bedrock configured in `us-east-1` with `CHRONOS_BEDROCK_MODEL_ID` so the narrative is really generated.
- [ ] Terminal with a large font and the full panel visible.
- [ ] Have a clear action (`attack the goblin`) and an ambiguous one (`hmm I don't know`) ready.

## Structure (approximate timing)

**0:00–0:20 — Hook and what it is**
"This is ChronosDecider, a real-time RPG Game Master. The twist: the decision of
what happens in the story is not made by an LLM, it's made by Strands Decider 2B
in milliseconds, and Amazon Bedrock only handles the narration."

**0:20–0:45 — The architecture in one sentence**
Show the README diagram (decision → triage → generation).
"Decider picks the branch with a calibrated confidence. If it's confident,
Bedrock narrates. If not, the agent asks instead of making things up."

**0:45–1:40 — Clear-action demo**
- Type `attack the goblin`.
- Point at the panel: **Decision via: strands-decider**, the chosen **branch**,
  the **confidence** and the **decision latency** (highlight the <100ms / ~115ms).
- Point at **Narrative via: bedrock** and read the generated narration.
"The decision came from the decision model; the text, from Bedrock. Each doing its job."

**1:40–2:20 — Guardrail demo (Human-in-the-Loop)**
- Type something ambiguous (`hmm I don't know what to do`).
- Show that **confidence drops below 0.70**, the **fallback** triggers and the
  agent **asks for clarification** instead of narrating.
"Here's the value of calibrated confidence: the agent knows when it does NOT know."

**2:20–2:45 — The reusable pattern**
- Open `decision_patterns/tool_selection.py` or its README.
"This decision is packaged as a reusable tool-selection pattern: swap the options
for your tools and drop it into your agent."

**2:45–3:00 — Closing**
"ChronosDecider. Fast, calibrated decisions with Strands Decider 2B, narration
with Bedrock. Repo and article in the description."

## Notes

- If you record without Bedrock, say it explicitly: "here I'm using the local
  template narrator; with Bedrock configured the text is generated" — honesty
  with the judges, never present the template as if it were Bedrock.
- ALWAYS highlight the moment the panel shows the confidence and the latency:
  that is the heart of the hackathon.
