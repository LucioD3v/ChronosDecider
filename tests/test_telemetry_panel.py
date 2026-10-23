"""Telemetry panel tests (`telemetry_panel`)."""

import unittest

from src.telemetry.telemetry_panel import TelemetryPanel


def _record(panel, latency_ms=10.0, confidence=0.9, fallback=False):
    return panel.record(
        latency_ms=latency_ms,
        confidence_score=confidence,
        action_type="COMBAT",
        target_branch="branch.combat",
        triggered_fallback=fallback,
    )


class TestTelemetryPanel(unittest.TestCase):
    def setUp(self):
        self.panel = TelemetryPanel()

    def test_summary_vacio_es_none(self):
        self.assertIsNone(self.panel.summary())

    def test_record_crea_entrada(self):
        rec = _record(self.panel)
        self.assertEqual(rec.latency_ms, 10.0)
        self.assertEqual(len(self.panel.records), 1)

    def test_historiales_en_orden_cronologico(self):
        _record(self.panel, confidence=0.1, latency_ms=5.0)
        _record(self.panel, confidence=0.9, latency_ms=20.0)
        self.assertEqual(self.panel.confidence_history, [0.1, 0.9])
        self.assertEqual(self.panel.latency_history, [5.0, 20.0])

    def test_summary_agrega_correctamente(self):
        _record(self.panel, latency_ms=10.0, confidence=0.4, fallback=True)
        _record(self.panel, latency_ms=30.0, confidence=0.8, fallback=False)
        s = self.panel.summary()
        self.assertEqual(s.total, 2)
        self.assertEqual(s.avg_latency_ms, 20.0)
        self.assertEqual(s.min_latency_ms, 10.0)
        self.assertEqual(s.max_latency_ms, 30.0)
        self.assertEqual(s.last_latency_ms, 30.0)
        self.assertAlmostEqual(s.avg_confidence, 0.6)
        self.assertEqual(s.last_confidence, 0.8)
        self.assertEqual(s.fallback_count, 1)

    def test_within_target_ratio(self):
        _record(self.panel, latency_ms=50.0)    # dentro de objetivo (<100ms)
        _record(self.panel, latency_ms=150.0)   # fuera de objetivo
        self.assertEqual(self.panel.summary().within_target_ratio, 0.5)

    def test_within_latency_target_por_record(self):
        rec_ok = _record(self.panel, latency_ms=50.0)
        rec_slow = _record(self.panel, latency_ms=150.0)
        self.assertTrue(rec_ok.within_latency_target)
        self.assertFalse(rec_slow.within_latency_target)

    def test_reset_vacia_historial(self):
        _record(self.panel)
        self.panel.reset()
        self.assertIsNone(self.panel.summary())

    def test_max_history_descarta_antiguos(self):
        panel = TelemetryPanel(max_history=2)
        _record(panel, confidence=0.1)
        _record(panel, confidence=0.2)
        _record(panel, confidence=0.3)
        self.assertEqual(panel.summary().total, 2)
        self.assertEqual(panel.confidence_history, [0.2, 0.3])


if __name__ == "__main__":
    unittest.main()
