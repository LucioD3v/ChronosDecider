"""Narrator tests (`narrator`): text generation and backend selection."""

import unittest

from src.engine.narrator import TemplateNarrator, build_default_narrator


class TestTemplateNarrator(unittest.TestCase):
    def setUp(self):
        self.narrator = TemplateNarrator()

    def test_source_es_template(self):
        self.assertEqual(self.narrator.source, "template")

    def test_narrate_devuelve_texto_no_vacio(self):
        texto = self.narrator.narrate("atacar al goblin", "combat", "COMBAT")
        self.assertTrue(texto.strip())
        self.assertIn("combat", texto)

    def test_narrate_entrada_vacia_no_rompe(self):
        texto = self.narrator.narrate("", "exploration", "EXPLORE")
        self.assertTrue(texto.strip())


class TestBuildDefaultNarrator(unittest.TestCase):
    def test_sin_bedrock_configurado_devuelve_template(self):
        # In the test environment BEDROCK_MODEL_ID is empty by default,
        # so the default narrator must be the local template one.
        narrator = build_default_narrator()
        self.assertEqual(narrator.source, "template")


if __name__ == "__main__":
    unittest.main()
