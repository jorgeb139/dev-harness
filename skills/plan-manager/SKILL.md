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

1. Si existe `docs/plans/ACTIVE-PLAN.md` con Estado "en progreso": PROHIBIDO empezar otro
   plan. Retomar la tarea marcada con ► o preguntar al usuario qué hacer con el plan activo.
2. Crear el plan usando el formato de `templates/PLAN-template.md` desde la raiz del repo/plugin dev-harness:
   - Etapas lógicamente agrupadas: cada etapa deja software funcional y testeable.
   - Cada etapa declara objetivos como criterios de éxito medibles, con la evidencia que
     los probará (comando y salida esperada).
   - Tareas numeradas N.M con checkbox.
3. Presentar el plan al usuario y obtener aprobación ANTES de ejecutar.
4. Al iniciar la ejecución: invocar la skill agent-orchestrator (pregunta modalidad de
   agentes, modelos y tokens) — obligatorio, no opcional.
5. Durante ejecución, tras terminar CADA tarea: marcar su checkbox y mover el marcador
   `**Tarea actual:** ► Etapa N, tarea N.M` a la siguiente. El plan desactualizado es un
   bug del proceso.
6. Al terminar todas las tareas de una etapa: invocar la skill stage-validator. PROHIBIDO
   iniciar la etapa siguiente sin su validación en verde escrita en el plan.
7. Al completar el plan: Estado → "completado", invocar la skill retrospective, y mover el
   archivo a `docs/plans/done/AAAA-MM-DD-<nombre>.md`.

## Regla permanente

En todo momento debe poder responderse leyendo el plan: ¿qué se está haciendo ahora mismo,
qué falta, y qué etapas ya fueron validadas?
