"""Tests del script de benchmark (`scripts/benchmark.py`)."""

import importlib.util
import os
import unittest

# El benchmark vive en scripts/ (no es un paquete). Lo cargamos por ruta.
_BENCH_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "benchmark.py"
)
_spec = importlib.util.spec_from_file_location("chronos_benchmark", _BENCH_PATH)
benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark)


class TestBenchmark(unittest.TestCase):
    def test_run_benchmark_estructura(self):
        report = benchmark.run_benchmark(50)
        self.assertEqual(report["iterations"], 50)
        for clave in ("latency_ms", "confidence", "within_latency_target_ratio",
                      "fallback_ratio"):
            self.assertIn(clave, report)
        for p in ("avg", "min", "max", "p50", "p90", "p95", "p99"):
            self.assertIn(p, report["latency_ms"])

    def test_ratios_en_rango(self):
        report = benchmark.run_benchmark(100)
        self.assertGreaterEqual(report["within_latency_target_ratio"], 0.0)
        self.assertLessEqual(report["within_latency_target_ratio"], 1.0)
        self.assertGreaterEqual(report["fallback_ratio"], 0.0)
        self.assertLessEqual(report["fallback_ratio"], 1.0)

    def test_histograma_suma_total(self):
        report = benchmark.run_benchmark(100)
        total = sum(b["count"] for b in report["confidence"]["histogram"])
        self.assertEqual(total, 100)

    def test_percentil_ordenado(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertEqual(benchmark._percentile(vals, 0), 1.0)
        self.assertEqual(benchmark._percentile(vals, 100), 5.0)
        self.assertEqual(benchmark._percentile(vals, 50), 3.0)


if __name__ == "__main__":
    unittest.main()
