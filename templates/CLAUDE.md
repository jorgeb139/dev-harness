@AGENTS.md

Consulta también `PROJECT-CONTEXT.md`, `.harness/plan.json` y `.harness/execution-state.json`.
Si la identidad local no coincide con `.harness/project-identity.json`, detente y no cargues
memoria, planes ni historial de otro proyecto.

## Dev Harness

Antes de modificar código, lee `ARCHITECTURE.md`, `MUST-DO.md` y el plan activo. Usa
`planning-director` para analizar impacto y `confidence-gate` para resolver incertidumbres.
Después de cada tarea, registra un checkpoint con `.harness/harness-state.py` y deja un
handoff con la siguiente acción exacta para el próximo agente.
