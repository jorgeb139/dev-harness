---
description: Inicializa el harness de calidad en el proyecto actual
---

Inicializa dev-harness en el proyecto actual (cwd). Pasos exactos:

1. Verificar que cwd es la raíz de un proyecto (existe .git o el usuario confirma). Si ya
   existe `.harness/health.sh`, avisar que ya está inicializado y preguntar antes de tocar nada.
2. Copiar plantillas desde el plugin (no sobrescribir archivos existentes; si existen, saltarlos y avisar):
   - `${CLAUDE_PLUGIN_ROOT}/templates/ARCHITECTURE.md` → `./ARCHITECTURE.md`
   - `${CLAUDE_PLUGIN_ROOT}/templates/MUST-DO.md` → `./MUST-DO.md`
   - `${CLAUDE_PLUGIN_ROOT}/templates/health.sh` → `./.harness/health.sh` (crear `.harness/`, dar permisos con `chmod +x`)
   - Crear directorio `docs/plans/` (los planes usan `${CLAUDE_PLUGIN_ROOT}/templates/PLAN-template.md` como formato)
3. Personalizar con el usuario, preguntando una cosa a la vez:
   - Stack del proyecto → completar sección Stack de `ARCHITECTURE.md`.
   - Comandos reales de build y test → escribirlos en `.harness/health.sh` (reemplazar el
     placeholder; debe terminar en < 60 segundos, usar subconjunto rápido de tests si la suite es lenta).
   - Reglas innegociables iniciales → `MUST-DO.md`.
4. Correr `bash .harness/health.sh` y mostrar el resultado. Si falla, ofrecer arreglar el
   proyecto como primera tarea.
5. Sugerir commit: `git add ARCHITECTURE.md MUST-DO.md .harness docs/plans && git commit -m "chore: inicializar dev-harness"`.
