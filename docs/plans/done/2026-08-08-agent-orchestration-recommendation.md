# Plan: recomendación automática de modalidad de agentes

- **Estado:** completado
- **Spec:** solicitud del usuario, 2026-08-08
- **Tarea actual:** completada
- **Rama base:** develop
- **Rama de tarea:** codex/checkpoint-handoffs
- **Integración:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Complejidad:** baja (T=3, F=5, S=1, R=bajo, D=corta)
- **Modalidad recomendada:** agente único — no hay riesgo alto ni paralelismo útil.
- **Modalidad elegida:** agente único
- **Estimación agente único:** 75k-150k tokens
- **Estimación multi-agente:** 190k-380k tokens
- **Estimación mixta:** 120k-220k tokens
- **Modelos por rol:** modelo actual para todo

## Etapa 1: decisión basada en complejidad

**Objetivos (criterios de éxito):**
- [ ] El harness clasifica cada plan por tareas, archivos, riesgo y duración.
- [ ] Presenta estimados de agente único y multi-agente, con supuestos y rango.
- [ ] Recomienda una modalidad explicando el motivo y permite que el usuario la cambie.
- [ ] `plan-manager` exige registrar recomendación, decisión y estimados.

**Tareas:**
- [x] 1.1 Rediseñar agent-orchestrator y su matriz de decisión.
- [x] 1.2 Integrar el registro en plan-manager, README y session-start.
- [x] 1.3 Actualizar tests y ejecutar validación completa.

**Validación de etapa:**
- [x] Seguridad revisada: rama de tarea correcta, `develop` presente, `git diff --check` en verde, sin secretos ni dependencias nuevas.
- [x] Regresión: `bash tests/validate.sh` -> `ALL OK`; `session-start.sh` muestra complejidad, recomendación y estimados.
- [x] Objetivos cumplidos: matriz `T/F/S/R/D`, tres modalidades, rangos de tokens, recomendación explicada y registro en plan.

Validación: seguridad ✅ | regresión ✅ (`bash tests/validate.sh`) | objetivos ✅ — 2026-08-08
