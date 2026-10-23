"""Decision client tests (`decider_client`)."""

import unittest

from src.engine.decider_client import (
    DeciderClient,
    DecisionResult,
    SimulatedDeciderBackend,
    StrandsDeciderHTTPBackend,
)

_OPTIONS = ["combat", "dialogue", "exploration", "flee", "interaction"]


class TestSimulatedBackend(unittest.TestCase):
    def setUp(self):
        self.backend = SimulatedDeciderBackend()

    def test_accion_clara_alta_certeza(self):
        r = self.backend.decide_branch("atacar al goblin", _OPTIONS)
        self.assertEqual(r.branch_id, "combat")
        self.assertEqual(r.action_type, "COMBAT")
        self.assertGreater(r.confidence_score, 0.70)
        self.assertEqual(r.source, "simulated")

    def test_keyword_ingles(self):
        r = self.backend.decide_branch("talk to the merchant", _OPTIONS)
        self.assertEqual(r.branch_id, "dialogue")

    def test_determinista(self):
        a = self.backend.decide_branch("explorar la cueva", _OPTIONS)
        b = self.backend.decide_branch("explorar la cueva", _OPTIONS)
        self.assertEqual((a.branch_id, a.confidence_score),
                         (b.branch_id, b.confidence_score))

    def test_intenciones_mezcladas_bajan_certeza(self):
        r = self.backend.decide_branch("atacar y huir", _OPTIONS)
        self.assertLessEqual(r.confidence_score, 0.70)

    def test_entrada_vacia_clarify(self):
        r = self.backend.decide_branch("", _OPTIONS)
        self.assertEqual(r.branch_id, "clarify")
        self.assertEqual(r.confidence_score, 0.0)

    def test_desconocido_clarify_baja_certeza(self):
        r = self.backend.decide_branch("xyzzy plugh", _OPTIONS)
        self.assertEqual(r.branch_id, "clarify")
        self.assertLessEqual(r.confidence_score, 0.70)

    def test_reporta_latencia(self):
        r = self.backend.decide_branch("atacar", _OPTIONS)
        self.assertGreaterEqual(r.decision_latency_ms, 0.0)


class TestHTTPBackendParsing(unittest.TestCase):
    """Tests the parsing of server responses without touching the network."""

    def setUp(self):
        self.backend = StrandsDeciderHTTPBackend(base_url="http://localhost:9999")

    def test_parse_choice_confidence(self):
        payload = {"answers": {"narrative_branch": {"choice": "combat", "confidence": 0.83}},
                   "latency_ms": 118.0}
        r = self.backend._parse(payload, _OPTIONS, latency_ms=120.0)
        self.assertEqual(r.branch_id, "combat")
        self.assertEqual(r.action_type, "COMBAT")
        self.assertAlmostEqual(r.confidence_score, 0.83)
        self.assertEqual(r.source, "strands-decider")
        self.assertEqual(r.server_latency_ms, 118.0)
        self.assertEqual(r.decision_latency_ms, 120.0)

    def test_parse_probabilities_argmax(self):
        payload = {"answers": {"narrative_branch": {
            "probabilities": {"combat": 0.1, "dialogue": 0.75, "flee": 0.15}}}}
        r = self.backend._parse(payload, _OPTIONS, latency_ms=10.0)
        self.assertEqual(r.branch_id, "dialogue")
        self.assertAlmostEqual(r.confidence_score, 0.75)

    def test_parse_opcion_fuera_de_catalogo_es_clarify(self):
        payload = {"answers": {"narrative_branch": {"choice": "teleport", "confidence": 0.99}}}
        r = self.backend._parse(payload, _OPTIONS, latency_ms=10.0)
        self.assertEqual(r.branch_id, "clarify")
        self.assertEqual(r.confidence_score, 0.0)


class TestDeciderClientFallback(unittest.TestCase):
    def test_backend_inyectado_se_usa_tal_cual(self):
        class FakeBackend:
            def decide_branch(self, player_input, options):
                return DecisionResult(
                    branch_id="combat", action_type="COMBAT",
                    confidence_score=0.9, source="fake", decision_latency_ms=1.0,
                )

        client = DeciderClient(backend=FakeBackend())
        r = client.decide("lo que sea")
        self.assertEqual(r.source, "fake")

    def test_backend_inyectado_no_hace_fallback_silencioso(self):
        class BrokenBackend:
            def decide_branch(self, player_input, options):
                raise ConnectionError("servidor caído")

        client = DeciderClient(backend=BrokenBackend())
        # Backend explícito -> el error se propaga, no cae al simulado.
        with self.assertRaises(ConnectionError):
            client.decide("atacar")

    def test_fallback_a_simulado_cuando_servidor_no_responde(self):
        # With no injected backend, the primary is HTTP to a closed port;
        # it must degrade to the simulated one without raising.
        client = DeciderClient()
        client._primary = StrandsDeciderHTTPBackend(base_url="http://127.0.0.1:9")
        r = client.decide("atacar al goblin")
        self.assertEqual(r.source, "simulated")
        self.assertEqual(r.branch_id, "combat")


if __name__ == "__main__":
    unittest.main()
