---
name: agent-orchestrator
description: Usar al INICIAR la ejecución de un plan aprobado, antes de la primera tarea. Pregunta al usuario modalidad (multi-agente vs agente único), qué modelos usar por tipo de trabajo, y presenta estimado de tokens de cada modalidad.
---

# agent-orchestrator

Antes de ejecutar la primera tarea de un plan aprobado, presentar al usuario UNA pregunta
con estas opciones y un estimado de tokens calculado para ESTE plan (ver fórmula abajo):

## Opción A — Multi-agente (calidad máxima)

- Un subagente fresco por tarea (implementador) + revisión independiente por tarea
  (revisor con contexto limpio) + validación de etapa por agente distinto al implementador.
- Modelos por defecto (ajustables por el usuario): arquitectura/revisión → modelo top
  (Opus o superior); implementación de tareas bien especificadas → modelo medio (Sonnet);
  tareas mecánicas (renombres, formateo, scaffolding) → modelo pequeño (Haiku).
- Costo: más tokens (cada subagente re-lee contexto). Beneficio: revisión cruzada real,
  contexto principal no se agota en sesiones largas.

## Opción B — Agente único (economía)

- Todo en esta sesión, mismo modelo actual. Checkpoints de revisión con el usuario por etapa.
- Costo: menos tokens. Riesgo: sin revisión independiente; contexto largo degrada precisión.

## Estimado de tokens (presentarlo siempre, como rango)

Contar tareas del plan (T) y estimar por experiencia: multi-agente ≈ T × (60k–120k) tokens
(implementador + revisor por tarea); agente único ≈ T × (25k–50k). Presentar ambos rangos
en tokens y aclarar que es estimado grueso, no promesa. Si el usuario tiene límite de
presupuesto, recomendar: multi-agente solo para etapas de riesgo (arquitectura, seguridad)
y agente único para el resto (modalidad mixta, ofrecerla como Opción C).

## Registro

Anotar la decisión (modalidad + modelos) al inicio del ACTIVE-PLAN.md y respetarla durante
toda la ejecución salvo que el usuario la cambie.
