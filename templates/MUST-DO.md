# MUST-DO — reglas innegociables de este proyecto

> Los agentes DEBEN cumplir cada regla. Cuando el usuario corrija la forma de trabajar,
> la corrección se agrega aquí con fecha. Nunca borrar reglas sin aprobación del usuario.

## Reglas

1. [AAAA-MM-DD] [regla]
2. [AAAA-MM-DD] Branch governance: todo trabajo va en rama nueva de tarea; prohibido commit/merge/push directo en `main`, `master` o `develop`.
3. [AAAA-MM-DD] El repo debe tener `develop` ademas de `main` o `master`; `develop` es staging. Si falta, crear `develop` desde `main`/`master` antes de features.
4. [AAAA-MM-DD] Integracion obligatoria por PR: rama de tarea -> `develop`; promocion separada `develop` -> `main`/`master`.
5. [AAAA-MM-DD] Prohibido aprobar o mergear PRs hacia `develop`, `main` o `master` salvo orden explicita del usuario que diga crear el PR y tambien aprobarlo/mergearlo.
6. [AAAA-MM-DD] El orquestador debe mostrar modalidad, modelos por rol y tokens estimados; el usuario decide ambos y el harness registra la decisión.
7. [AAAA-MM-DD] La identidad se valida antes de cargar contexto, memoria, plan o historial; ante mismatch se debe fallar cerrado.
