#!/usr/bin/env python
"""
ChronosDecider benchmark.

Runs a batch of simulated evaluations through the `DecisionEngine` and reports:
  * Decision latency in milliseconds: mean, min, max and p50/p90/p95/p99
    percentiles.
  * Confidence score distribution in bins (histogram).
  * Percentage of decisions within the latency target (<100ms).
  * Percentage of turns that triggered the fallback (Human-in-the-Loop).

It ALWAYS uses the deterministic simulated backend (it does not touch the model
server or Bedrock), so the benchmark is reproducible and runnable anywhere.
Standard library only.

Usage:
    python scripts/benchmark.py                 # 1000 iterations, text output
    python scripts/benchmark.py -n 5000         # custom iteration count
    python scripts/benchmark.py --json          # JSON output (for CI / dashboards)
    python scripts/benchmark.py --json -o out.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List

# Allows running the script directly (resolves the `src` package).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.engine import DeciderClient, DecisionEngine, SimulatedDeciderBackend
from src.engine.narrator import TemplateNarrator

# Sample actions covering the five branches, mixes (low confidence) and
# unknown/empty inputs (fallback). The benchmark cycles over them.
_SAMPLE_INPUTS: List[str] = [
    "attack the goblin",
    "talk to the merchant",
    "explore the dark cave",
    "flee from the dragon",
    "use the health potion",
    "open the chest",
    "ask for directions",
    "investigate the noise",
    "attack and then flee",      # mixed intent -> low confidence
    "hmm I don't know what to do",  # unknown -> fallback
    "",                          # empty -> fallback
]


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Percentile by linear interpolation. `pct` in [0, 100]."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[int(rank)]
    frac = rank - low
    return sorted_values[low] * (1 - frac) + sorted_values[high] * frac


def _confidence_histogram(values: List[float], bins: int = 10) -> List[Dict[str, Any]]:
    """Histogram of confidence over `bins` equal buckets on [0.0, 1.0]."""
    counts = [0] * bins
    for v in values:
        # Clamp and place in the matching bin (1.0 falls in the last bin).
        idx = min(bins - 1, max(0, int(v * bins)))
        counts[idx] += 1
    total = len(values) or 1
    histogram = []
    for i, c in enumerate(counts):
        histogram.append({
            "range": [round(i / bins, 2), round((i + 1) / bins, 2)],
            "count": c,
            "ratio": c / total,
        })
    return histogram


def run_benchmark(iterations: int) -> Dict[str, Any]:
    """Run `iterations` simulated evaluations and aggregate the metrics."""
    # Explicit simulated backend -> deterministic and network-free. Template
    # narrator so it does not depend on Bedrock.
    engine = DecisionEngine(
        decider=DeciderClient(backend=SimulatedDeciderBackend()),
        narrator=TemplateNarrator(),
    )

    latencies: List[float] = []
    confidences: List[float] = []
    fallbacks = 0
    within_target = 0

    for i in range(iterations):
        player_input = _SAMPLE_INPUTS[i % len(_SAMPLE_INPUTS)]
        result = engine.evaluate(player_input)
        latencies.append(result.decision_latency_ms)
        confidences.append(result.confidence_score)
        if result.trigger_fallback:
            fallbacks += 1
        if result.within_latency_target:
            within_target += 1

    latencies_sorted = sorted(latencies)
    total = len(latencies) or 1

    return {
        "iterations": iterations,
        "latency_ms": {
            "avg": sum(latencies) / total,
            "min": latencies_sorted[0] if latencies_sorted else 0.0,
            "max": latencies_sorted[-1] if latencies_sorted else 0.0,
            "p50": _percentile(latencies_sorted, 50),
            "p90": _percentile(latencies_sorted, 90),
            "p95": _percentile(latencies_sorted, 95),
            "p99": _percentile(latencies_sorted, 99),
        },
        "confidence": {
            "avg": sum(confidences) / total,
            "min": min(confidences) if confidences else 0.0,
            "max": max(confidences) if confidences else 0.0,
            "histogram": _confidence_histogram(confidences),
        },
        "within_latency_target_ratio": within_target / total,
        "fallback_ratio": fallbacks / total,
    }


def _bar(ratio: float, width: int = 30) -> str:
    filled = int(round(max(0.0, min(1.0, ratio)) * width))
    return "#" * filled + "." * (width - filled)


def print_report(report: Dict[str, Any]) -> None:
    """Print the report in a human-readable format."""
    lat = report["latency_ms"]
    conf = report["confidence"]
    line = "=" * 56

    print(line)
    print(" ChronosDecider \u2014 Benchmark (simulated backend)")
    print(line)
    print(f" Iterations             : {report['iterations']}")
    print()
    print(" Decision latency (ms)")
    print(f"   mean / min / max     : {lat['avg']:.4f} / {lat['min']:.4f} / {lat['max']:.4f}")
    print(f"   p50 / p90 / p95 / p99: {lat['p50']:.4f} / {lat['p90']:.4f} / "
          f"{lat['p95']:.4f} / {lat['p99']:.4f}")
    print(f"   within <100ms        : {report['within_latency_target_ratio']:.1%}")
    print()
    print(" Confidence score")
    print(f"   mean / min / max     : {conf['avg']:.3f} / {conf['min']:.3f} / {conf['max']:.3f}")
    print("   distribution (histogram):")
    for b in conf["histogram"]:
        lo, hi = b["range"]
        print(f"     [{lo:.1f}-{hi:.1f})  {b['count']:>6}  {_bar(b['ratio'])} {b['ratio']:.1%}")
    print()
    print(f" Fallback (Human-in-the-Loop): {report['fallback_ratio']:.1%} of turns")
    print(line)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ChronosDecider benchmark.")
    parser.add_argument("-n", "--iterations", type=int, default=1000,
                        help="Number of evaluations to run (default 1000).")
    parser.add_argument("--json", action="store_true",
                        help="Emit the report as JSON instead of text.")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="File path to save the JSON report.")
    args = parser.parse_args(argv)

    if args.iterations <= 0:
        parser.error("--iterations must be a positive integer.")

    report = run_benchmark(args.iterations)

    if args.json or args.output:
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"JSON report written to: {args.output}")
        if args.json:
            print(text)
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
