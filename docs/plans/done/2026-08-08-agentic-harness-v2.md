# Plan: agentic harness v2

- **Estado:** completado
- **Spec:** `docs/superpowers/specs/2026-08-08-agentic-harness-v2-design.md`
- **Tarea actual:** completada
- **Rama base:** develop
- **Rama de tarea:** codex/agentic-harness-v2
- **Integración:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Complejidad:** alta (T=9, F=15+, S=3, R=alto, D=larga)
- **Modalidad recomendada:** mixta — riesgo alto exige revisiones independientes, mientras el núcleo de estado y la integración son secuenciales.
- **Modalidad elegida:** mixta
- **Estimación agente único:** 225k-450k tokens
- **Estimación multi-agente:** 570k-1.14M tokens
- **Estimación mixta:** 395k-790k tokens
- **Modelos por rol:** modelo principal para integración; agente fuerte para planificación/seguridad; agente medio para implementación; agente pequeño para tareas mecánicas
- **Estado de ejecución:** `docs/plans/ACTIVE-PLAN.state.json`
- **Handoff:** `docs/plans/ACTIVE-PLAN.HANDOFF.md`

## Etapa 1: State engine and resumable handoff

**Objetivos (criterios de éxito):**
- [x] CLI de estado con transiciones válidas, validación y escritura atómica.
- [x] Handoff generado con siguiente acción, bloqueos, evidencia y último commit verificado.
- [x] Tests de transición, corrupción e interrupción en verde.

**Tareas:**
- [x] 1.1 State contract tests
- [x] 1.2 Implement the atomic state CLI
- [x] 1.3 State-engine regression coverage

**Validación de etapa:**
- [x] Seguridad revisada: rama de tarea correcta, `develop` presente, `git diff --check` en verde, sin secretos ni dependencias nuevas.
- [x] Regresión: `bash tests/test-harness-state.sh` y `bash tests/validate.sh` -> `ALL OK`; `.harness/health.sh` no aplica en este plugin.
- [x] Test strategy: CLI probado sin dependencias externas; cobertura de código del proyecto consumidor queda para Stage 2.
- [x] Handoff generado y validado por `harness-state.py`.
- [x] Objetivos cumplidos con evidencia: estados, transiciones, historial, lock, escritura atómica y `advance`.

Validación: seguridad ✅ | regresión ✅ (`bash tests/test-harness-state.sh` + `bash tests/validate.sh`) | objetivos ✅ — 2026-08-08

## Etapa 2: Director, safety, regression, and test-strategy roles

**Objetivos (criterios de éxito):**
- [x] Skills especializadas con entradas, salidas y gates obligatorios.
- [x] Plan registra impacto, preguntas abiertas, seguridad, regresión y estrategia de tests.
- [x] Política de 90%/100% y criterios integración/E2E documentados.

**Tareas:**
- [x] 2.1 Planning and security role skills
- [x] 2.2 Regression and test-strategy role skills
- [x] 2.3 Checkpoint role and plan schema

**Validación de etapa:**
- [x] Seguridad revisada: skills exigen secretos, permisos, inputs, rollback y confirmación; no hay dependencias nuevas.
- [x] Regresión revisada: `bash tests/validate.sh` -> `ALL OK`; la skill exige baseline, targeted y suite completa.
- [x] Test strategy revisada: 90% mínimo de código nuevo/modificado, 100% solo con coste bajo, integración/E2E condicionales.
- [x] Handoff actualizado: `harness-state.py checkpoint` y `advance` registraron evidencia real.
- [x] Objetivos cumplidos con evidencia: cinco skills, plantilla HANDOFF y campos de impacto/tests en PLAN.

Validación: seguridad ✅ | regresión ✅ (`bash tests/validate.sh`) | test strategy ✅ | handoff ✅ — 2026-08-08

## Etapa 3: Orchestration, hooks, initialization, and validation

**Objetivos (criterios de éxito):**
- [ ] Lifecycle completo conectado a plan-manager, stage-validator y hooks.
- [ ] Inicialización instala state CLI, memoria e importación de Claude.
- [ ] Suite completa y validaciones en verde; versión 0.3.0 registrada.

**Tareas:**
- [x] 3.1 Integrate lifecycle skills and hooks
- [x] 3.2 Initialize and document the orchestrator
- [x] 3.3 Full verification and handoff

**Validación de etapa:**
- [x] Seguridad ✅: branch correcta, `git diff --check`, scan de secretos sin hallazgos y sin dependencias nuevas.
- [x] Regresión ✅: `bash tests/test-harness-state.sh`, `bash tests/test-session-start.sh`, `bash tests/test-pre-commit-gate.sh`, `bash tests/validate.sh` -> `ALL OK`.
- [x] Test strategy ✅: unitarios del state engine y tests de integración de hooks; E2E no aplica a este plugin sin UI/API desplegable.
- [x] Handoff ✅: state válido y último commit verificado `507d112`.
- [x] Objetivos ✅: lifecycle, inicialización, `CLAUDE.md`, roles, gates y versión `0.3.0`.

Validación: seguridad ✅ | regresión ✅ | test strategy ✅ | handoff ✅ | objetivos ✅ — 2026-08-08
