"""Strict schema validator tests (`schema_validator`)."""

import unittest

from src.engine.schema_validator import (
    SchemaValidationError,
    validate_narrative_output,
)


def _valid_payload(**overrides):
    """Build a minimal valid payload; `overrides` lets you mutate it."""
    payload = {
        "action_type": "COMBAT",
        "target_branch": "branch.combat",
        "confidence_score": 0.9,
        "trigger_fallback": False,
        "narrative_response": "El GM interpreta la acción.",
    }
    payload.update(overrides)
    return payload


class TestSchemaValidator(unittest.TestCase):
    def test_payload_valido_pasa_y_se_devuelve(self):
        payload = _valid_payload()
        self.assertIs(validate_narrative_output(payload), payload)

    def test_latency_ms_opcional_permitido(self):
        payload = _valid_payload(latency_ms=12.3)
        self.assertIsNotNone(validate_narrative_output(payload))

    def test_falta_campo_requerido(self):
        payload = _valid_payload()
        del payload["target_branch"]
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(payload)

    def test_no_es_objeto(self):
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(["no", "soy", "un", "dict"])

    def test_tipo_incorrecto_en_string(self):
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(_valid_payload(action_type=123))

    def test_confidence_fuera_de_rango_superior(self):
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(_valid_payload(confidence_score=1.5))

    def test_confidence_fuera_de_rango_inferior(self):
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(_valid_payload(confidence_score=-0.1))

    def test_confidence_en_limites_es_valido(self):
        self.assertIsNotNone(validate_narrative_output(_valid_payload(confidence_score=0.0)))
        self.assertIsNotNone(validate_narrative_output(_valid_payload(confidence_score=1.0)))

    def test_booleano_no_es_numero_valido(self):
        # confidence_score is "number"; a bool must not slip through even though
        # in Python bool is a subclass of int.
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(_valid_payload(confidence_score=True))

    def test_trigger_fallback_debe_ser_boolean(self):
        with self.assertRaises(SchemaValidationError):
            validate_narrative_output(_valid_payload(trigger_fallback="no"))


if __name__ == "__main__":
    unittest.main()
