# Patrón de decisión reutilizable: Tool Selection

> Tags: `#strands-decider-2b` `#tool-selection`

Una receta que cualquier builder puede soltar en su propio agente para que
**Strands Decider 2B** elija qué herramienta (o rama) ejecutar a partir del
texto del usuario, con una **confianza calibrada** que sirve de guardrail: si la
decisión no es fiable, el agente pide aclaración en vez de actuar a ciegas.

Es independiente del resto del proyecto: copia la carpeta `decision_patterns/` a
tu repo y úsala. Solo usa la biblioteca estándar de Python (`urllib`).

## Los tres elementos del patrón

**1. La pregunta tipada y el conjunto de opciones**

Una pregunta `choice` de Decider: unas instrucciones en lenguaje natural y las
etiquetas de tus herramientas como opciones.

```python
from decision_patterns import ToolSelectionPattern

pattern = ToolSelectionPattern(
    instructions="¿Qué herramienta responde mejor al usuario?",
    options=["buscar_web", "consultar_db", "responder_directo"],
    confidence_threshold=0.70,
)
```

**2. El wiring en la ruta del agente** (gate tipo `before_tool_call`)

```python
choice = pattern.select(user_input)
if choice.should_act:
    resultado = ejecutar_herramienta(choice.tool)   # confianza > umbral
else:
    pedir_aclaracion_al_usuario(choice)             # guardrail: no actuar a ciegas
```

O como handler envuelto, listo para un InterventionHandler de Strands Agents:

```python
handler = pattern.as_intervention(
    execute=lambda tool: ejecutar_herramienta(tool),
    on_low_confidence=lambda ch: pedir_aclaracion_al_usuario(ch),
)
handler(user_input)
```

**3. Nota de uso**

- Levanta el servidor del modelo:
  `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000`
- Las opciones que pasas en `options` son las etiquetas exactas que Decider puede
  devolver. Mantenlas cortas y distintas entre sí.
- `confidence_threshold` controla el guardrail. La confianza de Decider está
  calibrada: por encima de ~0.9 acierta la gran mayoría de las veces; por debajo,
  confirma con una persona. Ajusta el umbral a tu tolerancia al riesgo.
- `select()` devuelve también `latency_ms`, útil para medir el ahorro frente a
  pedirle la decisión a un LLM generativo.

## Cómo lo usa ChronosDecider

ChronosDecider aplica exactamente este patrón: la acción del jugador es el
`state`, y las opciones son las ramas narrativas (`combat`, `dialogue`,
`exploration`, `flee`, `interaction`). Si la confianza supera el umbral, Amazon
Bedrock narra la rama; si no, el Game Master pide aclaración. Ver
`src/engine/decider_client.py`.

## Ejemplo ejecutable

`example.py` en esta carpeta muestra el patrón contra un servidor local. Si el
servidor no está corriendo, explica cómo levantarlo.
