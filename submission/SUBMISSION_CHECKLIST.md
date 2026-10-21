# Checklist de envío — Agent Experience Hackathon: Strands Decider

Fecha límite: **23 de octubre**. Requisitos tomados de las reglas oficiales.

## Obligatorio para calificar

- [ ] **Agente que usa Strands Decider 2B** para al menos una decisión
      significativa, **emparejado con Amazon Bedrock**.
      → Hecho en código: Decider decide la rama, Bedrock narra.
      → **Pendiente tú**: ejecutar con el servidor de Decider real + Bedrock real
        al menos para grabar el video.
- [ ] **Artículo en Builder Center** describiendo el agente, qué hace y la
      decisión entregada a Decider 2B.
      → Borrador en `submission/ARTICLE_DRAFT.md` (rellena los marcadores).
- [ ] **Repositorio público** con el código y **al menos un patrón de decisión
      reutilizable**.
      → Patrón en `decision_patterns/`. **Pendiente tú**: hacer el repo público.
- [ ] **Video demo público < 3 minutos** mostrando el agente y la decisión de
      Decider 2B funcionando.
      → Guion en `submission/VIDEO_SCRIPT.md`.
- [ ] **Un patrón de decisión declarado**: Tool selection.
- [ ] **Agente original**, no publicado antes.

## Tags (ambos, antes del deadline)

- [ ] `#strands-decider-2b`
- [ ] `#tool-selection`

## Recomendado (suma en la rúbrica)

- [ ] Medir y reportar latencia/coste de mover la decisión fuera del LLM
      (bonus en "Effective use of Decider 2B").
- [ ] Capturas del panel de telemetría en el artículo.

## Rúbrica (para enfocar el esfuerzo)

- Creatividad y factor "cool" — 30%
- Uso efectivo de Decider 2B (incl. calidad del patrón reutilizable) — 30%
- Calidad de comunicación (artículo + video) — 25%
- Originalidad — 15%
