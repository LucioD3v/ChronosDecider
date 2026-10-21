"""
Validador estricto de la salida del modelo contra `narrative_schema.json`.

Implementado SOLO con la biblioteca estándar (sin `jsonschema` ni otras
dependencias no especificadas). Cubre exactamente lo que el esquema declara:
tipos, campos requeridos y los límites numéricos de `confidence_score`.

Regla 2 de la arquitectura: la respuesta del modelo DEBE ser un objeto JSON
válido con `action_type`, `target_branch` y `confidence_score`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Dict

from ..config import NARRATIVE_SCHEMA_PATH


class SchemaValidationError(ValueError):
    """Se lanza cuando la salida del modelo no cumple el esquema narrativo."""


# Mapeo de los tipos de JSON Schema (draft-07) a tipos de Python.
# `bool` se trata aparte porque en Python `bool` es subclase de `int`.
_JSON_TYPE_TO_PY = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
}


@lru_cache(maxsize=1)
def _load_schema() -> Dict[str, Any]:
    """Carga y cachea el esquema narrativo desde disco.

    Se cachea porque el esquema es estático durante la ejecución y leerlo en
    cada evaluación penalizaría el objetivo de latencia (<100ms).
    """
    with NARRATIVE_SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _check_type(field: str, value: Any, json_type: str) -> None:
    """Valida el tipo de un único campo según el esquema."""
    expected = _JSON_TYPE_TO_PY.get(json_type)
    if expected is None:
        # Tipo declarado en el esquema que no soportamos: fallo explícito,
        # nunca una suposición silenciosa.
        raise SchemaValidationError(
            f"Tipo de esquema no soportado '{json_type}' para el campo '{field}'."
        )

    # Un booleano NO es un número válido aunque Python lo considere int.
    if json_type == "number" and isinstance(value, bool):
        raise SchemaValidationError(
            f"El campo '{field}' debe ser number, no boolean."
        )

    if not isinstance(value, expected):
        raise SchemaValidationError(
            f"El campo '{field}' debe ser de tipo '{json_type}', "
            f"se recibió {type(value).__name__}."
        )


def validate_narrative_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Valida un payload contra `narrative_schema.json`.

    Args:
        payload: objeto (dict) producido por el modelo/adaptador.

    Returns:
        El mismo `payload` si es válido (para encadenar llamadas).

    Raises:
        SchemaValidationError: si falta un campo requerido, un tipo no coincide
        o `confidence_score` queda fuera de [0.0, 1.0].
    """
    if not isinstance(payload, dict):
        raise SchemaValidationError(
            f"La salida del modelo debe ser un objeto JSON, "
            f"se recibió {type(payload).__name__}."
        )

    schema = _load_schema()
    properties: Dict[str, Any] = schema.get("properties", {})
    required = schema.get("required", [])

    # 1) Campos requeridos presentes.
    for field in required:
        if field not in payload:
            raise SchemaValidationError(
                f"Falta el campo requerido '{field}' en la salida del modelo."
            )

    # 2) Tipos y restricciones por campo (solo campos declarados en el esquema).
    for field, rules in properties.items():
        if field not in payload:
            continue  # Campo opcional ausente: permitido.

        value = payload[field]
        json_type = rules.get("type")
        if json_type:
            _check_type(field, value, json_type)

        # Restricciones numéricas (minimum / maximum) si el esquema las define.
        if json_type == "number":
            minimum = rules.get("minimum")
            maximum = rules.get("maximum")
            if minimum is not None and value < minimum:
                raise SchemaValidationError(
                    f"El campo '{field}'={value} es menor que el mínimo "
                    f"permitido {minimum}."
                )
            if maximum is not None and value > maximum:
                raise SchemaValidationError(
                    f"El campo '{field}'={value} supera el máximo "
                    f"permitido {maximum}."
                )

    return payload
