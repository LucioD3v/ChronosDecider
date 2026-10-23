"""
Minimal example of the Tool Selection pattern against a local Strands Decider server.

Run:
    strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000
and then:
    python decision_patterns/example.py
"""

from __future__ import annotations

import urllib.error

from decision_patterns import ToolSelectionPattern


def main() -> None:
    pattern = ToolSelectionPattern(
        instructions="Which team should handle this message?",
        options=["billing", "sales", "retail"],
        confidence_threshold=0.70,
    )

    message = "Help! My payouts have been failing for 3 days."
    try:
        choice = pattern.select(message)
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        print("Could not reach the Strands Decider server at "
              f"{pattern._url!r}: {exc}")
        print("Start it with:")
        print("  strands-decider serve "
              "StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000")
        return

    print(f"Message     : {message}")
    print(f"Choice      : {choice.tool}")
    print(f"Confidence  : {choice.confidence:.3f}")
    print(f"Should act? : {choice.should_act} (threshold {pattern.confidence_threshold})")
    print(f"Latency     : {choice.latency_ms:.1f} ms")
    if not choice.should_act:
        print("Guardrail   : confidence too low -> ask for clarification before acting.")


if __name__ == "__main__":
    main()
