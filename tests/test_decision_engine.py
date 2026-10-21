"""Tests del motor de decisión (`decision_engine`)."""

import unittest

from src.config import CONFIDENCE_FALLBACK_THRESHOLD
from src.engine.decider_client import DeciderClient, DeciderResponse
from src.engine.decision_engine import DecisionEngine


class _StubBackend:
    """Backend de prueba con confianza fija, para aislar la lógica del motor."""

    def __init__(self, confidence: float):
        self._confidence = confidence

    def classify(self, player_input, context):
        return DeciderResponse(
            action_type="COMBAT",
            target_branch="branch.combat",
            confidence_score=self._confidence,
            narrative_response="stub",
        )


def _engine_with_confidence(confidence: float) -> DecisionEngine:
    return DecisionEngine(decider=DeciderClient(backend=_StubBackend(confidence)))


class TestTriageFallback(unittest.TestCase):
    def test_alta_certeza_no_dispara_fallback(self):
        result = _engine_with_confidence(0.95).evaluate("atacar")
        self.assertFalse(result.trigger_fallback)
        self.assertIsNone(result.clarification_prompt)

    def test_certeza_en_umbral_dispara_fallback(self):
        # Regla: confidence_score <= 0.70 -> fallback (el límite exacto incluido).
        result = _engine_with_confidence(CONFIDENCE_FALLBACK_THRESHOLD).evaluate("x")
        self.assertTrue(result.trigger_fallback)
        self.assertIsNotNone(result.clarification_prompt)

    def test_certeza_bajo_umbral_dispara_fallback(self):
        result = _engine_with_confidence(0.40).evaluate("x")
        self.assertTrue(result.trigger_fallback)
        self.assertIn("certeza", result.clarification_prompt.lower())

    def test_justo_encima_del_umbral_no_dispara(self):
        result = _engine_with_confidence(0.71).evaluate("x")
        self.assertFalse(result.trigger_fallback)


class TestEvaluateContrato(unittest.TestCase):
    def test_payload_validado_y_completo(self):
        result = _engine_with_confidence(0.9).evaluate("atacar")
        for campo in ("action_type", "target_branch", "confidence_score",
                      "trigger_fallback", "narrative_response", "latency_ms"):
            self.assertIn(campo, result.payload)

    def test_latencia_es_positiva_y_dentro_objetivo(self):
        result = _engine_with_confidence(0.9).evaluate("atacar")
        self.assertGreaterEqual(result.latency_ms, 0.0)
        # El simulador/stub es trivial: debe estar muy por debajo de 100ms.
        self.assertTrue(result.within_latency_target)

    def test_accesores_coinciden_con_payload(self):
        result = _engine_with_confidence(0.9).evaluate("atacar")
        self.assertEqual(result.action_type, result.payload["action_type"])
        self.assertEqual(result.confidence_score, result.payload["confidence_score"])


class TestTelemetriaIntegrada(unittest.TestCase):
    def test_cada_evaluacion_registra_un_record(self):
        engine = _engine_with_confidence(0.9)
        engine.evaluate("atacar")
        engine.evaluate("atacar")
        self.assertEqual(engine.telemetry.summary().total, 2)

    def test_umbral_configurable(self):
        # Con umbral 0.5, una confianza de 0.6 NO debe disparar fallback.
        engine = DecisionEngine(
            decider=DeciderClient(backend=_StubBackend(0.6)),
            fallback_threshold=0.5,
        )
        self.assertFalse(engine.evaluate("x").trigger_fallback)


if __name__ == "__main__":
    unittest.main()
