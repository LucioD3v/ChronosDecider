#!/usr/bin/env python
"""
Pre-recording environment check for ChronosDecider.

Verifies, end to end, that the two real integrations are reachable BEFORE you
record the demo video:

  1. Strands Decider 2B HTTP server (the DECISION layer).
  2. Amazon Bedrock via boto3 (the GENERATION layer).

It never prints secrets. Credentials are read by boto3 from your local AWS
configuration (`aws configure`), never from this file.

Usage:
    python scripts/check_setup.py
"""

from __future__ import annotations

import os
import sys
import urllib.error

# Resolve the `src` package when run directly.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.config import (
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    DECIDER_SERVER_URL,
)
from src.engine.decider_client import StrandsDeciderHTTPBackend
from src.engine.narrator import BedrockNarrator

OK = "[ OK ]"
FAIL = "[FAIL]"


def check_decider() -> bool:
    """Confirm the Strands Decider server answers a real choice question."""
    print(f"\n== Strands Decider 2B ==  ({DECIDER_SERVER_URL})")
    backend = StrandsDeciderHTTPBackend()
    options = ["combat", "dialogue", "exploration", "flee", "interaction"]
    try:
        result = backend.decide_branch("I attack the goblin with my sword", options)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        print(f"{FAIL} Server not reachable: {exc}")
        print("      Start it with:")
        print("      strands-decider serve "
              "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000")
        return False
    except Exception as exc:  # noqa: BLE001 - surface anything else clearly
        print(f"{FAIL} Unexpected error talking to the server: {exc}")
        return False

    print(f"{OK} Decision received from source='{result.source}'")
    print(f"      branch={result.branch_id} action={result.action_type} "
          f"confidence={result.confidence_score:.3f} "
          f"latency={result.decision_latency_ms:.1f} ms")
    if result.source != "strands-decider":
        print("      WARNING: source is not 'strands-decider'. The demo fell back "
              "to the simulator; the real model did not answer.")
        return False
    return True


def check_bedrock() -> bool:
    """Confirm Bedrock generates text with the configured model."""
    print(f"\n== Amazon Bedrock ==  (region={BEDROCK_REGION}, model={BEDROCK_MODEL_ID or '(unset)'})")
    if not BEDROCK_MODEL_ID:
        print(f"{FAIL} CHRONOS_BEDROCK_MODEL_ID is not set.")
        print('      Set it, e.g.: $env:CHRONOS_BEDROCK_MODEL_ID = "amazon.nova-lite-v1:0"')
        return False
    try:
        narrator = BedrockNarrator()
        text = narrator.narrate("I attack the goblin", "combat", "COMBAT")
    except Exception as exc:  # noqa: BLE001 - boto3/credential/model errors vary
        print(f"{FAIL} Bedrock call failed: {type(exc).__name__}: {exc}")
        print("      Check: `aws configure` credentials, IAM bedrock:InvokeModel,")
        print("      the region, and that the model id exists in Model catalog.")
        return False

    preview = text if len(text) <= 160 else text[:157] + "..."
    print(f"{OK} Bedrock generated narration:")
    print(f"      {preview}")
    return True


def main() -> int:
    print("ChronosDecider \u2014 pre-recording setup check")
    decider_ok = check_decider()
    bedrock_ok = check_bedrock()

    print("\n== Summary ==")
    print(f" Strands Decider 2B : {'ready' if decider_ok else 'NOT ready'}")
    print(f" Amazon Bedrock     : {'ready' if bedrock_ok else 'NOT ready'}")
    if decider_ok and bedrock_ok:
        print("\nAll set. The demo will show Decision via: strands-decider and "
              "Narrative via: bedrock. You can record.")
        return 0
    print("\nNot fully ready. The demo still runs, but any component marked NOT "
          "ready will use its local fallback (simulated decision / template "
          "narration). See the messages above.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
