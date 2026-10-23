"""Tests de exportación de telemetría (`to_dict` / `export_json`)."""

import json
import tempfile
import unittest
from pathlib import Path

from src.telemetry.telemetry_panel import TelemetryPanel


def _poblar(panel):
    panel.record(latency_ms=10.0, confidence_score=0.9, action_type="COMBAT",
                 target_branch="branch.combat", triggered_fallback=False)
    panel.record(latency_ms=150.0, confidence_score=0.4, action_type="UNKNOWN",
                 target_branch="branch.clarify", triggered_fallback=True)


class TestToDict(unittest.TestCase):
    def test_vacio_summary_none(self):
        d = TelemetryPanel().to_dict()
        self.assertIsNone(d["summary"])
        self.assertEqual(d["records"], [])
        self.assertIn("exported_at", d)
        self.assertIn("latency_target_ms", d)

    def test_estructura_con_registros(self):
        panel = TelemetryPanel()
        _poblar(panel)
        d = panel.to_dict()
        self.assertEqual(d["summary"]["total"], 2)
        self.assertEqual(len(d["records"]), 2)
        # Campos derivados presentes en cada registro.
        for row in d["records"]:
            self.assertIn("timestamp_iso", row)
            self.assertIn("within_latency_target", row)

    def test_es_serializable_a_json(self):
        panel = TelemetryPanel()
        _poblar(panel)
        # No debe lanzar.
        json.dumps(panel.to_dict())


class TestExportJson(unittest.TestCase):
    def test_escribe_archivo_valido(self):
        panel = TelemetryPanel()
        _poblar(panel)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "telemetria.json"
            ruta = panel.export_json(str(destino))
            self.assertTrue(ruta.exists())
            cargado = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(cargado["summary"]["total"], 2)
            self.assertEqual(len(cargado["records"]), 2)

    def test_crea_directorios_anidados(self):
        panel = TelemetryPanel()
        _poblar(panel)
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "sub" / "dir" / "t.json"
            ruta = panel.export_json(str(destino))
            self.assertTrue(ruta.exists())


if __name__ == "__main__":
    unittest.main()
