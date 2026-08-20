---
description: Inicializa el harness de calidad en el proyecto actual
---

Inicializa dev-harness en el proyecto actual (cwd). En Codex, seguir estos mismos pasos manualmente; en Claude Code, este archivo funciona como comando slash. Pasos exactos:

1. Verificar que cwd es la raíz de un proyecto (existe .git o el usuario confirma). Si ya
   existe `.harness/project-identity.json`, avisar que ya está inicializado y no sobrescribir
   nada. Si existe una identidad pero no coincide con cwd/remoto, detenerse y pedir confirmación.
2. Aplicar branch-governance inicial: confirmar que existe `main` o `master`; confirmar que
   existe `develop` o crearla desde `main`/`master`; no hacer push remoto sin aprobación.
3. Copiar plantillas desde el plugin (no sobrescribir archivos existentes; si existen, saltarlos y avisar):
   - `<raiz-del-repo-dev-harness>/templates/ARCHITECTURE.md` → `./ARCHITECTURE.md`
   - `<raiz-del-repo-dev-harness>/templates/MUST-DO.md` → `./MUST-DO.md`
   - `<raiz-del-repo-dev-harness>/templates/AGENTS.md` → `./AGENTS.md`
   - `<raiz-del-repo-dev-harness>/templates/CLAUDE.md` → `./CLAUDE.md`
   - `<raiz-del-repo-dev-harness>/templates/HANDOFF-template.md` → `./docs/plans/HANDOFF-template.md`
   - `<raiz-del-repo-dev-harness>/scripts/harness-state.py` → `./.harness/harness-state.py` (crear `.harness/`)
   - `<raiz-del-repo-dev-harness>/scripts/harness_state.py` → `./.harness/harness_state.py` (módulo compañero requerido por el wrapper)
   - `<raiz-del-repo-dev-harness>/scripts/harness_store.py` → `./.harness/harness_store.py` (módulo compartido requerido por `harness_state.py`)
   - `<raiz-del-repo-dev-harness>/scripts/harness-project.py` → `./.harness/harness-project.py`
   - `<raiz-del-repo-dev-harness>/scripts/harness_context.py` → `./.harness/harness_context.py`
   - `<raiz-del-repo-dev-harness>/scripts/harness_memory.py` → `./.harness/harness_memory.py`
   - `<raiz-del-repo-dev-harness>/scripts/harness-plan.py` → `./.harness/harness-plan.py`
   - `<raiz-del-repo-dev-harness>/scripts/harness_plan.py` → `./.harness/harness_plan.py`
   - `<raiz-del-repo-dev-harness>/templates/health.sh` → `./.harness/health.sh` (crear `.harness/`, dar permisos con `chmod +x`)
   - `<raiz-del-repo-dev-harness>/templates/PROJECT-CONTEXT.md` → `./PROJECT-CONTEXT.md`
   - `<raiz-del-repo-dev-harness>/templates/MEMORY-README.md` → `./.harness/memory/README.md`
   - `<raiz-del-repo-dev-harness>/templates/COMPLETION-POLICY.md` → `./docs/plans/COMPLETION-POLICY.md`
   - `<raiz-del-repo-dev-harness>/templates/PLAN-template.md` se usa como referencia humana;
     la fuente operativa es `./.harness/plan.json` y su proyección generada.
   - Crear directorios `.harness/memory/`, `.harness/transactions/` y `docs/plans/`.
4. Personalizar con el usuario, preguntando una cosa a la vez:
   - Stack del proyecto → completar sección Stack de `ARCHITECTURE.md`.
   - Comandos reales de build y test → escribirlos en `.harness/health.sh` (reemplazar el
     placeholder; debe terminar en < 60 segundos, usar subconjunto rápido de tests si la suite es lenta).
   - Reglas innegociables iniciales → `MUST-DO.md`.
   - Decisiones de diseño y excepciones del proyecto → `AGENTS.md` y `ARCHITECTURE.md`.
5. Inicializar la identidad con `python3 .harness/harness-project.py identity init`, generar
   `PROJECT-CONTEXT.md` con `context init`, validar identidad/contexto, crear el plan JSON
   canónico y generar `docs/plans/ACTIVE-PLAN.md`. El estado JSON y el handoff se crean antes
   de ejecutar la primera tarea. Un contexto stale se refresca; un mismatch no se reutiliza.
6. Correr `bash .harness/health.sh` y mostrar el resultado. Si falla, ofrecer arreglar el
   proyecto como primera tarea.
7. Sugerir commit en rama de tarea: `git add AGENTS.md CLAUDE.md ARCHITECTURE.md MUST-DO.md PROJECT-CONTEXT.md .harness docs/plans && git commit -m "chore: inicializar dev-harness"`.
