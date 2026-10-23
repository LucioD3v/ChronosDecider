"""Resilience tests: malformed responses and runtime failures do not break."""

import unittest

from src.engine.decider_client import (
    DeciderClient,
    DecisionResult,
    _safe_confidence,
    _safe_latency,
)
from src.engine.decision_engine import DecisionEngine


class TestSafeConfidence(unittest.TestCase):
    def test_none_es_cero(self):
        self.assertEqual(_safe_confidence(None), 0.0)

    def test_no_numerico_es_cero(self):
        self.assertEqual(_safe_confidence("alto"), 0.0)
        self.assertEqual(_safe_confidence(object()), 0.0)

    def test_nan_e_inf_son_cero(self):
        self.assertEqual(_safe_confidence(float("nan")), 0.0)
        self.assertEqual(_safe_confidence(float("inf")), 0.0)

    def test_fuera_de_rango_se_recorta(self):
        self.assertEqual(_safe_confidence(1.5), 1.0)
        self.assertEqual(_safe_confidence(-0.3), 0.0)

    def test_valor_valido_se_respeta(self):
        self.assertAlmostEqual(_safe_confidence(0.83), 0.83)


class TestSafeLatency(unittest.TestCase):
    def test_none_queda_none(self):
        self.assertIsNone(_safe_latency(None))

    def test_no_numerico_queda_none(self):
        self.assertIsNone(_safe_latency("rapido"))

    def test_negativo_e_inf_quedan_none(self):
        self.assertIsNone(_safe_latency(-5))
        self.assertIsNone(_safe_latency(float("inf")))

    def test_valido_se_respeta(self):
        self.assertEqual(_safe_latency(118.0), 118.0)


class TestDecisionSanitizing(unittest.TestCase):
    """The client sanitizes malformed decisions instead of propagating."""

    def _client_que_devuelve(self, result):
        class _B:
            def decide_branch(self, player_input, options):
                return result
        # No explicit backend so decide()'s sanitizing applies;
        # we inject the backend as the primary directly.
        client = DeciderClient()
        client._primary = _B()
        client._explicit_backend = None
        return client

    def test_confidence_none_se_sanea_a_cero(self):
        bad = DecisionResult("combat", "COMBAT", None, "x", decision_latency_ms=1.0)  # type: ignore[arg-type]
        client = self._client_que_devuelve(bad)
        r = client.decide("atacar")
        self.assertEqual(r.confidence_score, 0.0)

    def test_rama_fuera_de_catalogo_va_a_clarify(self):
        bad = DecisionResult("teleport", "WARP", 0.99, "x", decision_latency_ms=1.0)
        client = self._client_que_devuelve(bad)
        r = client.decide("algo")
        self.assertEqual(r.branch_id, "clarify")
        self.assertEqual(r.confidence_score, 0.0)

    def test_clarify_se_respeta(self):
        ok = DecisionResult("clarify", "UNKNOWN", 0.4, "x", decision_latency_ms=1.0)
        client = self._client_que_devuelve(ok)
        r = client.decide("algo")
        self.assertEqual(r.branch_id, "clarify")
        self.assertAlmostEqual(r.confidence_score, 0.4)

    def test_backend_que_lanza_cae_a_simulado(self):
        class _Boom:
            def decide_branch(self, player_input, options):
                raise RuntimeError("unexpected model failure")
        client = DeciderClient()
        client._primary = _Boom()
        client._explicit_backend = None  # allows the silent fallback
        r = client.decide("atacar al goblin")
        self.assertEqual(r.source, "simulated")
        self.assertEqual(r.branch_id, "combat")


class TestNarratorResilience(unittest.TestCase):
    """If the narrator fails at runtime, the turn degrades without crashing the UI."""

    def test_narrador_que_lanza_usa_plantilla(self):
        class _StubDecider:
            def decide(self, player_input):
                return DecisionResult(
                    "combat", "COMBAT", 0.9, "stub", decision_latency_ms=0.5,
                )

        class _BrokenNarrator:
            @property
            def source(self):
                return "bedrock"

            def narrate(self, player_input, branch_id, action_type):
                raise RuntimeError("Bedrock throttling")

        engine = DecisionEngine(decider=_StubDecider(), narrator=_BrokenNarrator())
        result = engine.evaluate("atacar")
        # Does not propagate, narrates with the template and flags it in the source.
        self.assertFalse(result.trigger_fallback)
        self.assertTrue(result.narrative_response.strip())
        self.assertIn("template(error)", result.narrative_source)


if __name__ == "__main__":
    unittest.main()
