"""Decision engine tests (`decision_engine`): decision + triage + generation."""

import unittest

from src.config import CONFIDENCE_FALLBACK_THRESHOLD
from src.engine.decider_client import DecisionResult
from src.engine.decision_engine import DecisionEngine


class _StubDecider:
    """Test Decider: returns a fixed decision (isolates the engine logic)."""

    def __init__(self, branch_id="combat", action_type="COMBAT", confidence=0.9):
        self._result = DecisionResult(
            branch_id=branch_id, action_type=action_type,
            confidence_score=confidence, source="stub", decision_latency_ms=0.5,
        )

    def decide(self, player_input):
        return self._result


class _StubNarrator:
    """Test narrator: records whether it was called and returns fixed text."""

    def __init__(self):
        self.called = False

    @property
    def source(self):
        return "stub-narrator"

    def narrate(self, player_input, branch_id, action_type):
        self.called = True
        return f"narrativa de {branch_id}"


def _engine(confidence=0.9, branch_id="combat"):
    narrator = _StubNarrator()
    engine = DecisionEngine(
        decider=_StubDecider(branch_id=branch_id, confidence=confidence),
        narrator=narrator,
    )
    return engine, narrator


class TestTriageFallback(unittest.TestCase):
    def test_alta_certeza_narra_y_no_hace_fallback(self):
        engine, narrator = _engine(confidence=0.95)
        result = engine.evaluate("atacar")
        self.assertFalse(result.trigger_fallback)
        self.assertIsNone(result.clarification_prompt)
        self.assertTrue(narrator.called)
        self.assertEqual(result.narrative_response, "narrativa de combat")
        self.assertEqual(result.target_branch, "branch.combat")

    def test_certeza_en_umbral_dispara_fallback_y_no_narra(self):
        engine, narrator = _engine(confidence=CONFIDENCE_FALLBACK_THRESHOLD)
        result = engine.evaluate("algo ambiguo")
        self.assertTrue(result.trigger_fallback)
        self.assertIsNotNone(result.clarification_prompt)
        self.assertFalse(narrator.called)                 # no se narra lo poco fiable
        self.assertEqual(result.narrative_response, "")
        self.assertEqual(result.target_branch, "branch.clarify")

    def test_justo_encima_del_umbral_narra(self):
        engine, narrator = _engine(confidence=0.71)
        result = engine.evaluate("atacar")
        self.assertFalse(result.trigger_fallback)
        self.assertTrue(narrator.called)


class TestEvaluateContrato(unittest.TestCase):
    def test_payload_validado_y_completo(self):
        engine, _ = _engine(confidence=0.9)
        result = engine.evaluate("atacar")
        for campo in ("action_type", "target_branch", "confidence_score",
                      "trigger_fallback", "narrative_response", "latency_ms"):
            self.assertIn(campo, result.payload)

    def test_latencia_dentro_del_objetivo(self):
        engine, _ = _engine(confidence=0.9)
        result = engine.evaluate("atacar")
        self.assertGreaterEqual(result.decision_latency_ms, 0.0)
        self.assertTrue(result.within_latency_target)

    def test_fuentes_expuestas(self):
        engine, _ = _engine(confidence=0.9)
        result = engine.evaluate("atacar")
        self.assertEqual(result.decision_source, "stub")
        self.assertEqual(result.narrative_source, "stub-narrator")


class TestTelemetriaIntegrada(unittest.TestCase):
    def test_cada_evaluacion_registra_un_record(self):
        engine, _ = _engine(confidence=0.9)
        engine.evaluate("atacar")
        engine.evaluate("atacar")
        self.assertEqual(engine.telemetry.summary().total, 2)

    def test_umbral_configurable(self):
        narrator = _StubNarrator()
        engine = DecisionEngine(
            decider=_StubDecider(confidence=0.6),
            narrator=narrator,
            fallback_threshold=0.5,
        )
        result = engine.evaluate("x")
        self.assertFalse(result.trigger_fallback)  # 0.6 > 0.5
        self.assertTrue(narrator.called)


if __name__ == "__main__":
    unittest.main()
