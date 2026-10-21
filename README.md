# ChronosDecider

Motor narrativo RPG en tiempo real que convierte a **Strands Decider 2B** en un
Game Master ultrarrápido. Objetivo: **< 100 ms por decisión**.

## Qué hace

Cada acción del jugador (texto libre) se enruta por el Decision Engine, que:

1. Clasifica la intención vía Strands Decider 2B (adaptador `DeciderClient`).
2. Aplica **triage / Human-in-the-Loop**: si `confidence_score <= 0.70` activa un
   fallback y genera un prompt de aclaración.
3. Valida **estrictamente** la salida contra `.kiro/steer/narrative_schema.json`.
4. Registra **telemetría** (latencia en ms + historial de certeza) por decisión.

## Estructura del proyecto

```
ChronosDecider/
├── main.py                       # Punto de entrada: lanza la demo RPG
├── src/
│   ├── config.py                 # Umbrales y rutas (derivados de la arquitectura)
│   ├── engine/                   # Decision Engine
│   │   ├── decider_client.py     # Adaptador de Strands Decider 2B (+ backend simulado)
│   │   ├── schema_validator.py   # Validación estricta contra el esquema narrativo
│   │   └── decision_engine.py    # Orquestación: clasificar → triage → validar → telemetría
│   ├── telemetry/                # Panel de telemetría
│   │   └── telemetry_panel.py    # Latencia (ms) e historial de confidence score
│   └── ui/                       # UI / Demo RPG
│       └── cli_app.py            # CLI interactiva + panel de métricas en tiempo real
└── .kiro/steer/
    ├── system_architecture.md    # Reglas de arquitectura (fuente de verdad)
    └── narrative_schema.json     # Esquema JSON de la salida del modelo
```

## Requisitos

- **Python 3.10+** (probado con 3.14). Sin dependencias externas: solo biblioteca
  estándar.

## Ejecutar la demo

Desde la raíz del proyecto:

```bash
python main.py
```

Escribe acciones en lenguaje natural. Ejemplos:

- `atacar al goblin` → alta certeza, rama `branch.combat`
- `hablar con el mercader` → `branch.dialogue`
- `explorar la cueva` → `branch.exploration`
- `mmm no sé` → baja certeza → **fallback** (aclaración Human-in-the-Loop)

Comandos de control: `ayuda` / `help` / `?` y `salir` / `quit` / `exit`.

El panel muestra tras cada turno: acción clasificada, rama narrativa, nivel de
certeza, **latencia en ms frente al objetivo de 100 ms** y si se activó el fallback.

## Tests

Suite con `unittest` (biblioteca estándar, sin dependencias). Desde la raíz:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Cubre: validación estricta de esquema, backend simulado determinista, lógica de
triage/fallback (incluido el límite exacto `<= 0.70`) y agregados de telemetría.

## Uso programático

```python
from src.engine import DecisionEngine

engine = DecisionEngine()
result = engine.evaluate("atacar al goblin")

print(result.action_type)       # "COMBAT"
print(result.target_branch)     # "branch.combat"
print(result.confidence_score)  # 0.92
print(result.trigger_fallback)  # False
print(result.latency_ms)        # p. ej. 0.05

summary = engine.telemetry.summary()
print(summary.avg_latency_ms, summary.within_target_ratio)
```

## Integración del modelo real

El cliente `DeciderClient` usa por defecto un **backend simulado determinista**
(`SimulatedDeciderBackend`) para que el sistema funcione de extremo a extremo sin
el modelo. La arquitectura no especifica endpoint/SDK/transporte de Strands
Decider 2B, por lo que no se asume ninguno.

Para conectar el modelo real, implementa un backend que cumpla el `Protocol`
`DeciderBackend` (método `classify(player_input, context) -> DeciderResponse`) y
pásalo al cliente:

```python
from src.engine import DecisionEngine, DeciderClient

class StrandsDecider2BBackend:
    def classify(self, player_input, context):
        ...  # llamada al modelo real; devolver un DeciderResponse

engine = DecisionEngine(decider=DeciderClient(backend=StrandsDecider2BBackend()))
```

El resto del motor (triage, validación, telemetría, UI) no cambia. El punto de
integración está marcado con `TODO(integración-real)` en `src/engine/decider_client.py`.
