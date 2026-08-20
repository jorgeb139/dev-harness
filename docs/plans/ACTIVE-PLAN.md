# Plan: project-memory-orchestration

- **Estado:** en progreso
- **Spec:** `docs/superpowers/specs/2026-08-20-project-memory-orchestration-design.md`
- **Plan detallado:** `docs/superpowers/plans/2026-08-20-project-memory-orchestration.md`
- **Tarea actual:** ► Etapa 1, tarea 1.2
- **Rama base:** develop
- **Rama de tarea:** codex/project-memory-orchestration
- **Integracion:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Complejidad:** alta (T=9, F=25, S=4, R=alto, D=larga)
- **Modalidad recomendada:** multi-agente — riesgo alto, 9 tareas, 4 etapas y más de 8 archivos
- **Modalidad elegida:** multi-agente, subagente implementador y revisor independiente por tarea
- **Estimación agente único:** 225k-450k tokens
- **Estimación multi-agente:** 580k-1.16M tokens
- **Estimación mixta:** 465k-940k tokens
- **Modelos por rol:** revisión/arquitectura modelo de mayor capacidad; implementación modelo estándar; tareas mecánicas modelo rápido
- **Mapa de impacto:** scripts Python de estado, hooks Bash, comandos de inicialización, plantillas, skills, tests y manifiestos de plugin
- **Preguntas abiertas:** ninguna material; la modalidad fue elegida por el usuario
- **Estrategia de tests:** unitarios Python, integración de CLI, hooks y validación acumulativa; E2E no aplica al harness CLI
- **Cobertura objetivo:** >=90% del Python modificado; 100% si el coste marginal es bajo
- **Estado de seguridad:** pendiente
- **Estado de regresión:** pendiente
- **Estado de handoff:** pendiente

## Etapa 1: Persistent Foundations

**Objetivos:**
- [ ] Persistencia atómica, lock, fingerprints y detección de secretos probados.
- [ ] Identidad y contexto deterministas, con mismatch fail-closed.

**Tareas:**
- [x] 1.1 Extract shared storage primitives — implementado y revisado; commits `5dfa9a2`, `cdba8ae`
- [ ] 1.2 Add identity and deterministic project context

**Validación de etapa:** pendiente; requiere seguridad, regresión, tests y handoff en verde.

## Etapa 2: Memory and Structured Plans

**Objetivos:**
- [ ] Memoria de proyecto con promoción automática de instrucciones siempre y correcciones repetidas.
- [ ] Plan JSON canónico, Markdown generado y gates de dependencias/evidencia.

**Tareas:**
- [ ] 2.1 Implement project memory and learning promotion
- [ ] 2.2 Add canonical plan JSON and generated Markdown

**Validación de etapa:** pendiente.

## Etapa 3: Initialization, Hooks, and Role Contracts

**Objetivos:**
- [ ] Inicialización completa sin sobrescritura y carga de contexto en sesión.
- [ ] Hooks y skills alineados con identidad, memoria, revisión y elección de modalidad.

**Tareas:**
- [ ] 3.1 Upgrade initialization and templates
- [ ] 3.2 Update session and pre-commit enforcement
- [ ] 3.3 Align skills with the persisted workflow

**Validación de etapa:** pendiente.

## Etapa 4: Completion, Coverage, and Release

**Objetivos:**
- [ ] Archivado seguro de planes completos y retrospectiva.
- [ ] Cobertura >=90%, suite completa verde y versión 0.4.0.

**Tareas:**
- [ ] 4.1 Add completion/archive and retrospective integration
- [ ] 4.2 Run full verification, coverage, and version release

**Validación de etapa:** pendiente.

## Reglas de ejecución

- El orquestador dirige y cada tarea tiene implementador y revisor independientes.
- El implementador no amplía el scope; cualquier cambio de arquitectura, datos, permisos o contrato público pausa para aprobación.
- Cada tarea exige tests, revisión de seguridad, revisión de regresión, revisión de tests y checkpoint antes de avanzar.
- El mismo blocker se reintenta como máximo tres veces; después se persiste handoff y se marca bloqueado.
- El usuario elige la modalidad; el harness solo recomienda y estima.
