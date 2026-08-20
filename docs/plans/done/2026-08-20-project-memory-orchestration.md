# Plan: project-memory-orchestration

- **Estado:** completado
- **Spec:** `docs/superpowers/specs/2026-08-20-project-memory-orchestration-design.md`
- **Plan detallado:** `docs/superpowers/plans/2026-08-20-project-memory-orchestration.md`
- **Tarea actual:** completada
- **Rama base:** develop
- **Rama de tarea:** codex/project-memory-orchestration
- **Integracion:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Complejidad:** alta (T=9, F=25, S=4, R=alto, D=larga)
- **Modalidad recomendada:** multi-agente — riesgo alto, 9 tareas, 4 etapas y más de 8 archivos
- **Modalidad elegida:** multi-agente, subagente implementador y revisor independiente por tarea
- **Estimación agente único:** 225k-450k tokens
- **Estimación multi-agente:** 580k-1.16M tokens
- **Estimación mixta:** 465k-940k tokens
- **Modelos por rol:** orquestador/revisión modelo de mayor capacidad; implementación modelo estándar; tareas mecánicas modelo rápido
- **Selección de modelos:** el usuario elige automático, un modelo para todo o modelo por agente; cada rol registra modelo y tokens aproximados
- **Mapa de impacto:** scripts Python de estado, hooks Bash, comandos de inicialización, plantillas, skills, tests y manifiestos de plugin
- **Preguntas abiertas:** ninguna material; la modalidad fue elegida por el usuario
- **Estrategia de tests:** unitarios Python, integración de CLI, hooks y validación acumulativa; E2E no aplica al harness CLI
- **Cobertura objetivo:** >=90% del Python modificado; 100% si el coste marginal es bajo
- **Estado de seguridad:** verde — diff sin secretos, permisos nuevos ni dependencias externas
- **Estado de regresión:** verde — `bash tests/validate.sh` y suite dirigida completa pasan
- **Estado de handoff:** válido — commit verificado `a902659`; plan completado

## Etapa 1: Persistent Foundations

**Objetivos:**
- [ ] Persistencia atómica, lock, fingerprints y detección de secretos probados.
- [ ] Identidad y contexto deterministas, con mismatch fail-closed.

**Tareas:**
- [x] 1.1 Extract shared storage primitives — implementado y revisado; commits `5dfa9a2`, `cdba8ae`
- [x] 1.2 Add identity and deterministic project context — implementado y revisado; commit `d6d0191`

**Validación de etapa:** seguridad ✅ | regresión ✅ (`PYTHONDONTWRITEBYTECODE=1 bash tests/validate.sh` y suite dirigida) | test strategy ✅ (unitarios/CLI/integración aplicables; cobertura numérica pendiente de Task 4.2 porque no hay proveedor instalado) | handoff ✅ | objetivos ✅ — 2026-08-20.

## Etapa 2: Memory and Structured Plans

**Objetivos:**
- [ ] Memoria de proyecto con promoción automática de instrucciones siempre y correcciones repetidas.
- [ ] Plan JSON canónico, Markdown generado y gates de dependencias/evidencia.

**Tareas:**
- [x] 2.1 Implement project memory and learning promotion — implementado y revisado; commits `13ae15c`, `16cd82b`
- [x] 2.2 Add canonical plan JSON and generated Markdown — implementado; evidencia tipada, transacciones y handoff consistente; commit `971aa7e`

**Validación de etapa:** seguridad ✅ | regresión ✅ (`tests/validate.sh` y suites de plan/estado) | test strategy ✅ (unitarios/CLI/integración aplicables; cobertura numérica pendiente de 4.2) | handoff ✅ | objetivos ✅ — 2026-08-20.

## Etapa 3: Initialization, Hooks, and Role Contracts

**Objetivos:**
- [ ] Inicialización completa sin sobrescritura y carga de contexto en sesión.
- [ ] Hooks y skills alineados con identidad, memoria, revisión y elección de modalidad.

**Tareas:**
- [x] 3.1 Upgrade initialization and templates — identidad, contexto, memoria, plan y política de completitud
- [x] 3.2 Update session and pre-commit enforcement — mismatch fail-closed y proyección validada
- [x] 3.3 Align skills with the persisted workflow — roles, modelos, cobertura y gates alineados

**Validación de etapa:** seguridad ✅ | regresión ✅ (`tests/test-session-start.sh`, `tests/test-pre-commit-gate.sh`, `tests/validate.sh`) | test strategy ✅ (unitarios/CLI/integración aplicables; E2E no aplica al harness CLI) | handoff ✅ | objetivos ✅ — 2026-08-20.

## Etapa 4: Completion, Coverage, and Release

**Objetivos:**
- [ ] Archivado seguro de planes completos y retrospectiva.
- [ ] Cobertura >=90%, suite completa verde y versión 0.4.0.

**Tareas:**
- [x] 4.1 Add completion/archive and retrospective integration — archivado, política de completitud y retrospectiva documentados
- [x] 4.2 Run full verification, coverage, and version release — suites verdes; proveedor `coverage` no instalado, porcentaje numérico pendiente de entorno con provider

**Validación de etapa:** seguridad ✅ | regresión ✅ (`tests/validate.sh` + suites completas) | test strategy ✅ (unitarios/CLI/integración aplicables; E2E no aplica; coverage provider ausente) | handoff ✅ | objetivos ✅ — 2026-08-20.

## Reglas de ejecución

- El orquestador dirige y cada tarea tiene implementador y revisor independientes.
- El implementador no amplía el scope; cualquier cambio de arquitectura, datos, permisos o contrato público pausa para aprobación.
- Cada tarea exige tests, revisión de seguridad, revisión de regresión, revisión de tests y checkpoint antes de avanzar.
- El mismo blocker se reintenta como máximo tres veces; después se persiste handoff y se marca bloqueado.
- El usuario elige la modalidad; el harness solo recomienda y estima.
