---
name: project-context
description: Inicializa, valida y refresca identidad y contexto determinista del proyecto.
---

# project-context

Al iniciar una sesión, validar `.harness/project-identity.json` contra la raíz, nombre y
remoto actual. Solo después cargar `PROJECT-CONTEXT.md`, memoria, plan o historial.

El contexto contiene hechos detectados: manifests, runtimes, estructura, tests, scripts y
comandos. Propósitos, riesgos o despliegues no detectados se marcan explícitamente como
`Not detected; user/agent must verify`; nunca se inventan. Un fingerprint stale se refresca
con aprobación operativa; un mismatch falla cerrado y aísla toda la memoria del proyecto.
