# Plan: guardrails de simplicidad y memoria de proyecto

- **Estado:** completado
- **Spec:** conversación del usuario, 2026-08-08
- **Tarea actual:** completada
- **Rama base:** develop
- **Rama de tarea:** codex/engineering-guardrails
- **Integración:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Modalidad de agentes:** agente único (confirmada por el usuario)

## Etapa 1: reglas de ingeniería y memoria explícita

**Objetivos (criterios de éxito):**
- [ ] Un proyecto inicializado recibe reglas breves de simplicidad, dependencias, modularidad y compatibilidad segura.
- [ ] Los cambios destructivos tienen una regla explícita de verificación y confirmación.
- [ ] La documentación explica qué estado persiste y cómo se recupera entre sesiones.
- [ ] El validador del harness cubre las nuevas piezas.

**Tareas:**
- [x] 1.1 Crear la plantilla AGENTS.md y la skill destructive-changes.
- [x] 1.2 Integrar las piezas en init, session-start, README y tests.
- [x] 1.3 Ejecutar validación completa y registrar evidencia.

**Validación de etapa** (obligatoria antes de cerrar):
- [x] Seguridad revisada: rama `codex/engineering-guardrails`, `develop` presente, `git diff --check` en verde, sin secretos ni dependencias nuevas.
- [x] Regresión: `bash tests/validate.sh` -> `ALL OK`; `.harness/health.sh` no aplica porque este repo no lo tiene configurado.
- [x] Objetivos cumplidos: plantilla AGENTS, skill destructiva, integración de init/session-start/README/tests y memoria documentada.

Validación: seguridad ✅ | regresión ✅ (`bash tests/validate.sh`) | objetivos ✅ — 2026-08-08
