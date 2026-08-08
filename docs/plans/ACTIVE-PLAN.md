# Plan: agentic harness v2

- **Estado:** en progreso
- **Spec:** `docs/superpowers/specs/2026-08-08-agentic-harness-v2-design.md`
- **Tarea actual:** ► Etapa 1, tarea 1.1
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
- [ ] CLI de estado con transiciones válidas, validación y escritura atómica.
- [ ] Handoff generado con siguiente acción, bloqueos, evidencia y último commit verificado.
- [ ] Tests de transición, corrupción e interrupción en verde.

**Tareas:**
- [ ] 1.1 State contract tests
- [ ] 1.2 Implement the atomic state CLI
- [ ] 1.3 State-engine regression coverage

**Validación de etapa:**
- [ ] Seguridad revisada (secretos, inputs, permisos, dependencias)
- [ ] Regresión: suite completa de tests en verde (pegar comando y resumen de salida)
- [ ] Test strategy: cobertura y capas registradas
- [ ] Handoff generado y validado
- [ ] Objetivos cumplidos con evidencia

## Etapa 2: Director, safety, regression, and test-strategy roles

**Objetivos (criterios de éxito):**
- [ ] Skills especializadas con entradas, salidas y gates obligatorios.
- [ ] Plan registra impacto, preguntas abiertas, seguridad, regresión y estrategia de tests.
- [ ] Política de 90%/100% y criterios integración/E2E documentados.

**Tareas:**
- [ ] 2.1 Planning and security role skills
- [ ] 2.2 Regression and test-strategy role skills
- [ ] 2.3 Checkpoint role and plan schema

**Validación de etapa:**
- [ ] Seguridad revisada
- [ ] Regresión revisada
- [ ] Test strategy revisada
- [ ] Handoff actualizado
- [ ] Objetivos cumplidos con evidencia

## Etapa 3: Orchestration, hooks, initialization, and validation

**Objetivos (criterios de éxito):**
- [ ] Lifecycle completo conectado a plan-manager, stage-validator y hooks.
- [ ] Inicialización instala state CLI, memoria e importación de Claude.
- [ ] Suite completa y validaciones en verde; versión 0.3.0 registrada.

**Tareas:**
- [ ] 3.1 Integrate lifecycle skills and hooks
- [ ] 3.2 Initialize and document the orchestrator
- [ ] 3.3 Full verification and handoff

**Validación de etapa:**
- [ ] Seguridad ✅
- [ ] Regresión ✅
- [ ] Test strategy ✅
- [ ] Handoff ✅
- [ ] Objetivos ✅
