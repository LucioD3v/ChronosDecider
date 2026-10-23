#!/usr/bin/env python
"""
Benchmark de ChronosDecider.

Ejecuta un lote de evaluaciones simuladas a través del `DecisionEngine` y reporta:
  * Latencia de la decisión en milisegundos: media, mín, máx y percentiles
    p50/p90/p95/p99.
  * Distribución del confidence score en bins (histograma).
  * Porcentaje de decisiones dentro del objetivo de latencia (<100ms).
  * Porcentaje de turnos que activaron el fallback (Human-in-the-Loop).

Usa SIEMPRE el backend simulado determinista (no toca el servidor del modelo ni
Bedrock), para que el benchmark sea reproducible y ejecutable en cualquier parte.
Solo biblioteca estándar.

Uso:
    python scripts/benchmark.py                 # 1000 iteraciones, salida de texto
    python scripts/benchmark.py -n 5000         # nº de iteraciones personalizado
    python scripts/benchmark.py --json          # salida JSON (para CI / dashboards)
    python scripts/benchmark.py --json -o out.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List

# Permite ejecutar el script directamente (resuelve el paquete `src`).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.engine import DeciderClient, DecisionEngine, SimulatedDeciderBackend
from src.engine.narrator import TemplateNarrator

# Acciones de ejemplo que cubren las cinco ramas, mezclas (baja certeza) y
# entradas desconocidas/vacías (fallback). El benchmark cicla sobre ellas.
_SAMPLE_INPUTS: List[str] = [
    "atacar al goblin",
    "hablar con el mercader",
    "explorar la cueva oscura",
    "huir del dragón",
    "usar la poción de vida",
    "abrir el cofre",
    "preguntar por el camino",
    "investigar el ruido",
    "atacar y luego huir",       # intención mezclada -> baja certeza
    "mmm no sé qué hacer",       # desconocida -> fallback
    "",                          # vacía -> fallback
]


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Percentil por interpolación lineal. `pct` en [0, 100]."""
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
    """Histograma de confidence en `bins` tramos iguales sobre [0.0, 1.0]."""
    counts = [0] * bins
    for v in values:
        # Clampa y ubica en el bin correspondiente (1.0 cae en el último bin).
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
    """Ejecuta `iterations` evaluaciones simuladas y agrega las métricas."""
    # Backend simulado explícito -> determinista y sin red. Narrador de plantilla
    # para no depender de Bedrock.
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
    """Imprime el reporte en formato legible."""
    lat = report["latency_ms"]
    conf = report["confidence"]
    line = "=" * 56

    print(line)
    print(" ChronosDecider — Benchmark (backend simulado)")
    print(line)
    print(f" Iteraciones            : {report['iterations']}")
    print()
    print(" Latencia de decisión (ms)")
    print(f"   media / mín / máx    : {lat['avg']:.4f} / {lat['min']:.4f} / {lat['max']:.4f}")
    print(f"   p50 / p90 / p95 / p99: {lat['p50']:.4f} / {lat['p90']:.4f} / "
          f"{lat['p95']:.4f} / {lat['p99']:.4f}")
    print(f"   dentro de <100ms     : {report['within_latency_target_ratio']:.1%}")
    print()
    print(" Confidence score")
    print(f"   media / mín / máx    : {conf['avg']:.3f} / {conf['min']:.3f} / {conf['max']:.3f}")
    print("   distribución (histograma):")
    for b in conf["histogram"]:
        lo, hi = b["range"]
        print(f"     [{lo:.1f}-{hi:.1f})  {b['count']:>6}  {_bar(b['ratio'])} {b['ratio']:.1%}")
    print()
    print(f" Fallback (Human-in-the-Loop): {report['fallback_ratio']:.1%} de los turnos")
    print(line)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark de ChronosDecider.")
    parser.add_argument("-n", "--iterations", type=int, default=1000,
                        help="Número de evaluaciones a ejecutar (por defecto 1000).")
    parser.add_argument("--json", action="store_true",
                        help="Emite el reporte en JSON en vez de texto.")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Ruta de archivo para guardar el reporte JSON.")
    args = parser.parse_args(argv)

    if args.iterations <= 0:
        parser.error("--iterations debe ser un entero positivo.")

    report = run_benchmark(args.iterations)

    if args.json or args.output:
        text = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"Reporte JSON escrito en: {args.output}")
        if args.json:
            print(text)
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
