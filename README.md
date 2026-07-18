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
- `dev-harness:agent-orchestrator`: decide modalidad multi-agente vs agente unico y estima tokens.
- `dev-harness:retrospective`: captura lecciones y propone mejoras con aprobacion del usuario.
- `dev-harness:branch-governance`: impone ramas nuevas, `develop` obligatorio y PRs protegidos.

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
- `templates/health.sh` -> `.harness/health.sh`
- crear `docs/plans/`

Luego personaliza `ARCHITECTURE.md`, `MUST-DO.md` y `.harness/health.sh` con el stack, reglas y comandos reales del proyecto.

## Que impone

- **plan-manager**: tareas complejas exigen plan por etapas en `docs/plans/ACTIVE-PLAN.md`.
- **stage-validator**: cada etapa cierra con validacion de seguridad, regresion y objetivos con evidencia.
- **confidence-gate**: regla 95%; sin certeza verificada, se pregunta; prohibido inventar.
- **agent-orchestrator**: al ejecutar un plan pregunta modalidad de agentes, modelos y estimado de tokens.
- **retrospective**: al cerrar planes propone mejoras al propio harness; el usuario aprueba.
- **branch-governance**: todo trabajo va en rama nueva; `develop` es staging obligatorio; la integracion ocurre por PR rama->develop y luego PR develop->main/master.
- **Hooks Claude Code**: health-check al iniciar sesion y gate antes de `git commit`, incluyendo bloqueo de commits/merges directos en ramas protegidas.

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
