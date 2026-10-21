"""Tests del narrador (`narrator`): generación de texto y selección de backend."""

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
        # En el entorno de test BEDROCK_MODEL_ID está vacío por defecto,
        # así que el narrador por defecto debe ser el de plantilla local.
        narrator = build_default_narrator()
        self.assertEqual(narrator.source, "template")


if __name__ == "__main__":
    unittest.main()
