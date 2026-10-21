"""Tests del adaptador y el backend simulado (`decider_client`)."""

import unittest

from src.engine.decider_client import (
    DeciderClient,
    DeciderResponse,
    SimulatedDeciderBackend,
)


class TestDeciderResponse(unittest.TestCase):
    def test_to_payload_contiene_campos_del_esquema(self):
        resp = DeciderResponse(
            action_type="COMBAT",
            target_branch="branch.combat",
            confidence_score=0.92,
            narrative_response="texto",
        )
        payload = resp.to_payload()
        self.assertEqual(
            set(payload.keys()),
            {"action_type", "target_branch", "confidence_score",
             "trigger_fallback", "narrative_response"},
        )
        self.assertFalse(payload["trigger_fallback"])


class TestSimulatedBackend(unittest.TestCase):
    def setUp(self):
        self.backend = SimulatedDeciderBackend()

    def test_accion_clara_alta_certeza(self):
        r = self.backend.classify("atacar al goblin", {})
        self.assertEqual(r.action_type, "COMBAT")
        self.assertEqual(r.target_branch, "branch.combat")
        self.assertGreater(r.confidence_score, 0.70)

    def test_keyword_ingles(self):
        r = self.backend.classify("talk to the merchant", {})
        self.assertEqual(r.action_type, "DIALOGUE")

    def test_determinista_misma_entrada_misma_salida(self):
        a = self.backend.classify("explorar la cueva", {})
        b = self.backend.classify("explorar la cueva", {})
        self.assertEqual(a.to_payload(), b.to_payload())

    def test_intenciones_mezcladas_bajan_certeza(self):
        # "atacar" (COMBAT) + "huir" (FLEE) -> intención ambigua.
        r = self.backend.classify("atacar y huir", {})
        self.assertLessEqual(r.confidence_score, 0.70)

    def test_entrada_vacia_certeza_cero(self):
        r = self.backend.classify("", {})
        self.assertEqual(r.action_type, "UNKNOWN")
        self.assertEqual(r.confidence_score, 0.0)

    def test_intencion_desconocida_certeza_baja(self):
        r = self.backend.classify("xyzzy plugh", {})
        self.assertEqual(r.action_type, "UNKNOWN")
        self.assertLessEqual(r.confidence_score, 0.70)


class TestDeciderClient(unittest.TestCase):
    def test_usa_backend_simulado_por_defecto(self):
        client = DeciderClient()
        r = client.classify("atacar", None)
        self.assertEqual(r.action_type, "COMBAT")

    def test_acepta_backend_personalizado(self):
        class FakeBackend:
            def classify(self, player_input, context):
                return DeciderResponse(
                    action_type="CUSTOM",
                    target_branch="branch.x",
                    confidence_score=0.5,
                    narrative_response="fake",
                )

        client = DeciderClient(backend=FakeBackend())
        r = client.classify("lo que sea")
        self.assertEqual(r.action_type, "CUSTOM")


if __name__ == "__main__":
    unittest.main()
