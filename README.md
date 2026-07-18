# dev-harness

Plugin de Claude Code que impone estándares de calidad en desarrollo agéntico.

## Instalación en una máquina

```bash
claude plugin marketplace add /Users/jorge/Projects/dev-harness
claude plugin install dev-harness@dev-harness-marketplace
```

## Uso en un proyecto nuevo

Dentro del proyecto, correr `/dev-harness:init`. Crea `ARCHITECTURE.md`, `MUST-DO.md`,
`docs/plans/` y `.harness/health.sh` (chequeo de salud propio del proyecto).

## Qué impone

- **plan-manager**: tareas complejas exigen plan por etapas en `docs/plans/ACTIVE-PLAN.md`.
- **stage-validator**: cada etapa cierra con validación de seguridad + regresión + objetivos con evidencia.
- **confidence-gate**: regla 95% — sin certeza verificada, se pregunta; prohibido inventar.
- **agent-orchestrator**: al ejecutar un plan pregunta multi-agente vs único, modelos y estimado de tokens.
- **retrospective**: al cerrar planes propone mejoras al propio harness (el usuario aprueba).
- **Hooks**: health-check del proyecto al iniciar sesión; gate antes de `git commit`.

## Tests

```bash
bash tests/validate.sh
```
