---
name: retrospective
description: Usar al COMPLETAR un plan (o al cerrar una etapa especialmente problemática). Captura lecciones de la ejecución y propone mejoras concretas al propio harness; el usuario aprueba o rechaza cada propuesta. El harness nunca se auto-modifica sin aprobación.
---

# retrospective

## 1. Recolectar lecciones (de la sesión y el historial del plan)

- Errores cometidos por agentes y cómo se detectaron (¿los atrapó un gate del harness o
  el usuario?).
- Correcciones que dio el usuario ("no lo hagas así, hazlo asá").
- Preguntas que el usuario respondió y que el agente debió hacer ANTES (violaciones de
  confidence-gate).
- Validaciones de etapa que dejaron pasar un problema.
- Fricción: pasos del proceso que costaron tiempo sin aportar calidad.

## 2. Clasificar destino de cada lección

- Regla específica de ESTE proyecto → proponer línea nueva en `MUST-DO.md` del proyecto.
- Decisión arquitectural → proponer entrada en `ARCHITECTURE.md` del proyecto.
- Falla del PROCESO general → proponer edición concreta a una skill, hook, plantilla o
  script del repo del harness (`/Users/jorge/Projects/dev-harness`): mostrar diff exacto.

## 3. Aprobación (obligatoria)

Presentar propuestas UNA por una: qué cambia, por qué (con el incidente que lo motivó), y
el diff. El usuario aprueba, rechaza o edita cada una. PROHIBIDO aplicar cambios al harness
sin aprobación explícita de cada propuesta.

## 4. Aplicar

- Aprobadas de proyecto: editar MUST-DO.md / ARCHITECTURE.md y commitear en el proyecto.
- Aprobadas del harness: editar en `/Users/jorge/Projects/dev-harness`, correr
  `bash tests/validate.sh` (debe quedar en verde), commitear con mensaje
  `improve: <lección> (retro de <proyecto>)`, y subir versión patch en
  `.claude-plugin/plugin.json`.

## Branch governance al cierre

Antes de cerrar un plan, confirmar que el trabajo quedo en rama de tarea y que la siguiente
accion de integracion es PR hacia `develop`. Prohibido aprobar o mergear hacia `develop`,
`main` o `master` salvo orden explicita del usuario.
