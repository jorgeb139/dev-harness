---
name: branch-governance
description: Usar ANTES de modificar archivos, commitear, pushear, abrir PRs o cerrar una tarea. Impone rama nueva por tarea, develop obligatorio como staging, y PRs obligatorios hacia develop y luego main/master. Prohibe aprobar o mergear PRs salvo orden explicita del usuario.
---

# branch-governance

## Regla base

Todo trabajo de tarea se hace en una rama nueva. Prohibido trabajar directo en `main`,
`master` o `develop`, salvo tareas administrativas explicitamente autorizadas por el usuario
como crear la rama `develop` inicial.

## Ramas obligatorias

1. El repo debe tener una rama de produccion: `main` o `master`.
2. El repo debe tener `develop`. Si no existe, crear `develop` desde `main`/`master` antes
   de empezar trabajo de feature, documentarlo y pedir/aplicar aprobacion si la operacion
   requiere push remoto.
3. Las ramas de tarea deben partir de `develop` cuando existe. Si `develop` acaba de crearse,
   partir desde esa rama.
4. Nombre recomendado de rama: `codex/<descripcion-corta>` o el prefijo que el usuario pida.

## Flujo de integracion obligatorio

1. Al terminar una tarea, abrir PR desde la rama de tarea hacia `develop`.
2. No aprobar ni mergear ese PR salvo que el usuario lo pida explicitamente.
3. Para promover a produccion, abrir un PR separado desde `develop` hacia `main` o `master`.
4. No aprobar ni mergear el PR hacia `main`/`master` salvo que el usuario diga explicitamente
   que quiere abrir el PR y tambien aprobarlo/mergearlo.
5. Nunca hacer merge directo, push directo, commit directo o force-push a `main`, `master` o
   `develop` durante trabajo normal.

## Checklist antes de tocar archivos

- `git status --short` limpio o cambios existentes identificados como ajenos.
- Rama actual no es `main`, `master` ni `develop`.
- Existe `develop`; si no existe, crearla desde `main`/`master`.
- La rama de tarea parte de `develop`.

## Checklist al cerrar tarea

- Tests/verificaciones en verde con evidencia.
- Commit en la rama de tarea.
- PR propuesto o abierto hacia `develop`.
- No aprobacion ni merge sin instruccion explicita del usuario.

## Excepcion

La unica excepcion es una instruccion explicita del usuario. Debe nombrar la accion concreta:
por ejemplo, "crea el PR a develop y mergealo" o "aprueba el PR a main". Una instruccion general
como "termina esto" no autoriza aprobar ni mergear PRs protegidos.
