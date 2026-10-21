# Guion del video demo (< 3 minutos)

> Objetivo del jurado: ver el agente funcionando y, sobre todo, ver la decisión
> de Decider 2B en acción. Mantenlo por debajo de 3:00. Graba a 1080p.

## Checklist antes de grabar

- [ ] Servidor de Decider corriendo: `strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --port 8000`
- [ ] (Opcional pero recomendado) Bedrock configurado en `us-east-1` con `CHRONOS_BEDROCK_MODEL_ID` para que la narrativa sea generada real.
- [ ] Terminal con fuente grande y panel visible completo.
- [ ] Tener a mano una acción clara (`atacar al goblin`) y una ambigua (`mmm no sé`).

## Estructura (tiempos orientativos)

**0:00–0:20 — Gancho y qué es**
"Este es ChronosDecider, un Game Master de RPG en tiempo real. La gracia: la
decisión de qué pasa en la historia no la toma un LLM, la toma Strands Decider
2B en milisegundos, y Amazon Bedrock solo se encarga de narrar."

**0:20–0:45 — La arquitectura en una frase**
Muestra el diagrama del README (decisión → triage → generación).
"Decider decide la rama con una confianza calibrada. Si confía, Bedrock narra.
Si no, el agente pregunta en vez de inventar."

**0:45–1:40 — Demo acción clara**
- Escribe `atacar al goblin`.
- Señala en el panel: **Decisión vía: strands-decider**, la **rama** elegida, la
  **confianza** y la **latencia de decisión** (resalta el <100ms / ~115ms).
- Señala **Narrativa vía: bedrock** y lee la narración generada.
"La decisión fue del modelo de decisión; el texto, de Bedrock. Cada uno en lo suyo."

**1:40–2:20 — Demo guardrail (Human-in-the-Loop)**
- Escribe algo ambiguo (`mmm no sé qué hacer`).
- Muestra que la **confianza cae por debajo de 0.70**, se activa el **fallback** y
  el agente **pide aclaración** en lugar de narrar.
"Aquí está el valor de la confianza calibrada: el agente sabe cuándo NO sabe."

**2:20–2:45 — El patrón reutilizable**
- Abre `decision_patterns/tool_selection.py` o su README.
"Esta decisión está empaquetada como un patrón reutilizable de tool selection:
cambias las opciones por tus herramientas y lo sueltas en tu agente."

**2:45–3:00 — Cierre**
"ChronosDecider. Decisiones rápidas y calibradas con Strands Decider 2B,
narrativa con Bedrock. Repo y artículo en la descripción."

## Notas

- Si grabas sin Bedrock, di explícitamente "aquí uso el narrador local de
  plantilla; con Bedrock configurado el texto es generado" — honestidad ante el
  jurado, nunca presentes la plantilla como si fuera Bedrock.
- Resalta SIEMPRE el momento en que el panel muestra la confianza y la latencia:
  es el corazón de la hackathon.
