---
name: plan-manager
description: Usar ANTES de implementar cualquier tarea que toque 3+ archivos, agregue una feature nueva, o cambie arquitectura. Obliga a crear y mantener un plan por etapas en docs/plans/ACTIVE-PLAN.md con marcador de tarea actual siempre actualizado.
---

# plan-manager

## Umbral de complejidad

Aplicar este flujo si la tarea cumple CUALQUIERA: (a) toca 3+ archivos, (b) feature nueva
visible para el usuario, (c) cambia arquitectura o dependencias, (d) estimada en más de
una hora de trabajo. Si no lo cumple: trabajar directo, sin plan.

## Flujo obligatorio

0. Invocar `branch-governance` antes de tocar archivos: confirmar/crear `develop`, crear rama
   nueva de tarea desde `develop`, y registrar rama base/rama de tarea en el plan.
1. Si existe `docs/plans/ACTIVE-PLAN.md` con Estado "en progreso": PROHIBIDO empezar otro
   plan. Retomar la tarea marcada con ► o preguntar al usuario qué hacer con el plan activo.
2. Invocar `planning-director` antes de aprobar el plan. El director debe crear el mapa de
   impacto, resolver preguntas materiales con `confidence-gate` y registrar evidencia.
3. Crear el plan usando el formato de `templates/PLAN-template.md` desde la raiz del repo/plugin dev-harness:
   - Etapas lógicamente agrupadas: cada etapa deja software funcional y testeable.
   - Cada etapa declara objetivos como criterios de éxito medibles, con la evidencia que
     los probará (comando y salida esperada).
   - Tareas numeradas N.M con checkbox.
4. Presentar el plan al usuario y obtener aprobación ANTES de ejecutar.
5. Al iniciar la ejecución: invocar la skill agent-orchestrator (clasifica complejidad,
   recomienda modalidad, presenta estimados de tokens y pide confirmación) — obligatorio,
   no opcional. Registrar `T/F/S/R/D`, recomendación, decisión, motivo, estimados y modelos
   en `ACTIVE-PLAN.md` antes de ejecutar la primera tarea.
6. Durante ejecución, tras terminar CADA tarea: marcar su checkbox, ejecutar `checkpoint` y
   `advance`, y mover el marcador
   `**Tarea actual:** ► Etapa N, tarea N.M` a la siguiente. El plan desactualizado es un
   bug del proceso.
7. Al terminar todas las tareas de una etapa: invocar la skill stage-validator. PROHIBIDO
   iniciar la etapa siguiente sin su validación en verde escrita en el plan.
8. Al completar el plan: Estado → "completado", ejecutar `complete`, invocar la skill retrospective, y mover el
   archivo a `docs/plans/done/AAAA-MM-DD-<nombre>.md`.

## Regla permanente

En todo momento debe poder responderse leyendo el plan: ¿qué se está haciendo ahora mismo,
qué falta, y qué etapas ya fueron validadas?
