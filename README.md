# dev-harness

Harness de calidad para desarrollo agentico. Funciona como plugin de Claude Code y como plugin/skills de Codex.

## Instalacion en Codex

### Opcion recomendada: plugin Codex local

El repo incluye `.codex-plugin/plugin.json`, por lo que puede instalarse como plugin local de Codex desde un marketplace personal o de equipo.

Durante desarrollo local, la forma mas simple para que Codex descubra las skills es correr:

```bash
bash scripts/install-codex-skills.sh
```

El script crea el symlink `~/.agents/skills/dev-harness` de forma idempotente. Despues abre una tarea nueva en Codex para que el runtime vuelva a descubrir las skills.

### Skills disponibles en Codex

- `dev-harness:plan-manager`: exige plan por etapas para tareas complejas.
- `dev-harness:confidence-gate`: regla 95%; verificar o preguntar antes de suponer.
- `dev-harness:stage-validator`: cierra etapas con seguridad, regresion y objetivos con evidencia.
- `dev-harness:agent-orchestrator`: clasifica complejidad, recomienda agente único, modalidad mixta o multi-agente y estima tokens.
- `dev-harness:retrospective`: captura lecciones y propone mejoras con aprobacion del usuario.
- `dev-harness:branch-governance`: impone ramas nuevas, `develop` obligatorio y PRs protegidos.
- `dev-harness:destructive-changes`: frena eliminaciones de datos, APIs, permisos y otros cambios irreversibles.
- `dev-harness:planning-director`: analiza impacto, flujos, componentes, dependencias y preguntas antes de implementar.
- `dev-harness:security-review`: gate de secretos, permisos, inputs, datos, migraciones y rollback.
- `dev-harness:regression-review`: baseline, regresiones dirigidas y suite completa sin desactivar tests.
- `dev-harness:test-strategy`: decide unitarios, integración, E2E y cobertura mínima de 90% según arquitectura.
- `dev-harness:checkpoint-handoff`: persiste estado, evidencia, bloqueos y siguiente acción para otro agente.

## Instalacion en Claude Code

```bash
claude plugin marketplace add /Users/jorge/Projects/dev-harness
claude plugin install dev-harness@dev-harness-marketplace
```

## Uso en un proyecto nuevo

En Claude Code, dentro del proyecto, correr `/dev-harness:init`.

En Codex, pide: "inicializa dev-harness en este proyecto". El agente debe copiar las plantillas desde este repo sin sobrescribir archivos existentes:

- `templates/ARCHITECTURE.md` -> `ARCHITECTURE.md`
- `templates/MUST-DO.md` -> `MUST-DO.md`
- `templates/AGENTS.md` -> `AGENTS.md`
- `templates/CLAUDE.md` -> `CLAUDE.md`
- `templates/HANDOFF-template.md` -> `docs/plans/HANDOFF-template.md`
- `scripts/harness-state.py` -> `.harness/harness-state.py`
- `templates/health.sh` -> `.harness/health.sh`
- crear `docs/plans/`

Luego personaliza `AGENTS.md`, `ARCHITECTURE.md`, `MUST-DO.md` y `.harness/health.sh` con el stack, reglas y comandos reales del proyecto.

## Que impone

- **plan-manager**: tareas complejas exigen plan por etapas en `docs/plans/ACTIVE-PLAN.md`.
- **stage-validator**: cada etapa cierra con validacion de seguridad, regresion y objetivos con evidencia.
- **confidence-gate**: regla 95%; sin certeza verificada, se pregunta; prohibido inventar.
- **agent-orchestrator**: al ejecutar un plan calcula `T/F/S/R/D`, recomienda modalidad, muestra los tres estimados y registra la decisión del usuario.
- **retrospective**: al cerrar planes propone mejoras al propio harness; el usuario aprueba.
- **branch-governance**: todo trabajo va en rama nueva; `develop` es staging obligatorio; la integracion ocurre por PR rama->develop y luego PR develop->main/master.
- **destructive-changes**: cambios irreversibles requieren impacto, rollback y confirmacion explicita.
- **AGENTS.md**: concentra defaults de simplicidad, reutilizacion de dependencias, modularidad y compatibilidad segura.
- **planning-director**: no permite iniciar implementación con impacto o preguntas materiales sin resolver.
- **security-review**: revisa seguridad antes y después de la implementación.
- **regression-review**: exige baseline, tests dirigidos, suite completa y documentación de fallos.
- **test-strategy**: mínimo 90% de cobertura del código nuevo/modificado; integración y E2E cuando la arquitectura lo exige.
- **checkpoint-handoff**: mantiene el estado recuperable mediante `.harness/harness-state.py` y `ACTIVE-PLAN.HANDOFF.md`.
- **Hooks Claude Code**: health-check al iniciar sesion y gate antes de `git commit`, incluyendo bloqueo de commits/merges directos en ramas protegidas.

## Memoria del harness

El harness no tiene una base de datos de memoria semantica propia. La memoria persistente
del proyecto vive en archivos versionables: `AGENTS.md` contiene criterios de ingenieria,
`ARCHITECTURE.md` decisiones estables, `MUST-DO.md` reglas aprobadas y
`docs/plans/ACTIVE-PLAN.md` el trabajo en curso. Git conserva el historial y permite
recuperar decisiones anteriores. En cada inicio de sesion, `session-start.sh` inyecta
reglas y el resumen del plan activo; el contexto conversacional del agente es temporal y
no debe considerarse persistente hasta quedar escrito en esos archivos.

Para produccion, no uses `AGENTS.md` como sustituto de backups, auditoria, migraciones o
documentacion operativa.

## Orquestador y recuperación

El proyecto inicializado usa `python3 .harness/harness-state.py` para persistir el ciclo:

```text
pending -> in_progress -> blocked -> in_progress -> completed
```

Comandos principales: `init`, `start`, `checkpoint`, `advance`, `block`, `resume`,
`complete`, `show` y `validate`. Si el estado es inválido, el siguiente commit se bloquea
para evitar perder el punto de reanudación.

## Politica de ramas

- Todo repo debe tener `main` o `master` y tambien `develop`.
- `develop` se usa como staging. Si falta, se crea desde `main`/`master` antes de empezar features.
- Cada tarea se trabaja en una rama nueva desde `develop`, normalmente `codex/<descripcion>`.
- Al terminar, se abre PR de la rama de tarea hacia `develop`.
- Para produccion, se abre PR separado de `develop` hacia `main`/`master`.
- No se aprueba ni mergea ningun PR hacia `develop`, `main` o `master` salvo instruccion explicita del usuario que diga hacerlo.

## Compatibilidad

- Codex consume las skills desde `skills/*/SKILL.md` y el manifiesto `.codex-plugin/plugin.json`.
- Claude Code consume `.claude-plugin/plugin.json`, `commands/`, `hooks/` y los mismos `skills/`.
- Los scripts deben fallar abierto ante errores propios para no bloquear una sesion por culpa del harness.
- Las skills deben evitar depender de variables exclusivas de un runtime. Cuando necesiten plantillas, deben referirse a la raiz del repo/plugin y dar alternativa manual.

## Desarrollo

Ejecuta el validador acumulativo antes de cerrar cambios:

```bash
bash tests/validate.sh
```

El validador usa solo bash y `python3` del sistema para seguir siendo portable en macOS limpio.
