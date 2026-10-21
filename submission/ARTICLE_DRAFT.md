# ChronosDecider: un Game Master que decide con Strands Decider 2B y narra con Bedrock

> Borrador del artículo para Builder Center.
> Tags obligatorios al publicar: `#strands-decider-2b` `#tool-selection`
>
> Rellena los `[[marcadores]]` antes de publicar (enlaces, cifras medidas, capturas).

## El problema

En un RPG de texto en tiempo real, cada acción del jugador obliga al agente a
tomar una decisión: ¿esto es combate, diálogo, exploración, huida o interacción?
Si le pides esa decisión a un LLM generativo, pagas latencia y tokens por algo
que no necesita prosa, y el modelo tiende a elegir con una seguridad que no
tiene. El jugador nota los tiempos muertos y las decisiones raras.

## La idea

Separar **decidir** de **narrar**:

- **Strands Decider 2B** toma la decisión. Recibe la acción del jugador como
  estado y una pregunta tipada `choice` con las cinco ramas como opciones.
  Devuelve la rama y una **confianza calibrada**, sin generar texto.
- **Amazon Bedrock** hace lo que sí es generativo: narra la rama elegida como
  un Game Master.
- Si la confianza de Decider es baja (`<= 0.70`), el agente **no narra**: pide
  aclaración al jugador (Human-in-the-Loop). La confianza calibrada del modelo
  es justo la señal que permite este guardrail.

## La decisión que le di a Decider 2B

Una pregunta `choice`: *"Dada la acción del jugador, ¿qué rama narrativa
corresponde?"* con opciones `combat, dialogue, exploration, flee, interaction`.
Es una decisión de **tool selection**: la rama elegida determina qué
"herramienta" narrativa ejecuta el agente a continuación.

## El patrón reutilizable

El repo incluye `decision_patterns/tool_selection.py`, independiente del juego:
construye la pregunta `choice`, llama al servidor de Decider y devuelve la
elección con su confianza y un flag `should_act` que aplica el umbral como
guardrail. Se puede envolver como un gate `before_tool_call` para cualquier
agente de Strands. Otro builder lo copia, cambia las opciones por sus
herramientas, y lo tiene funcionando.

## Qué aprendí

- La confianza **calibrada** es la pieza que cambia el diseño: sin ella no
  tendría una señal fiable para decidir cuándo pedir ayuda. `[[comenta aquí tu
  experiencia con la calibración observada]]`
- Separar decisión y generación deja el código más limpio: cada modelo hace lo
  que sabe hacer.
- `[[opcional: mejora de latencia/coste medida al mover la decisión fuera del
  LLM — incluye cifras reales de tu ejecución con el servidor de Decider]]`

## Cómo ejecutarlo

Repositorio: `[[enlace al repo público]]`

```bash
# 1) Servir el modelo de decisión
pip install strands-decider
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000

# 2) (Opcional) Habilitar Bedrock en us-east-1 y exportar CHRONOS_BEDROCK_MODEL_ID
# 3) Ejecutar la demo
python main.py
```

Sin el servidor ni Bedrock, la demo corre con backends locales para que
cualquiera pueda probar el flujo.

## Demo

`[[enlace al video < 3 min]]`
