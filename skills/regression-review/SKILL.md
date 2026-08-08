---
name: regression-review
description: Usar antes de cerrar cada etapa para identificar flujos afectados, comparar una línea base y ejecutar regresiones completas.
---

# regression-review

## Preparación

Antes de implementar, registrar qué flujos, componentes y contratos podrían cambiar y qué
tests los cubren. Ejecutar la línea base disponible si el proyecto está sano.

## Revisión

Después de cada tarea:

1. Ejecutar tests dirigidos a los flujos afectados.
2. Ejecutar la suite completa y el health-check configurado.
3. Comparar el resultado con la línea base.
4. Revisar cambios de API, configuración, datos y comportamiento observable.
5. Registrar fallos, causa, decisión y siguiente acción en el handoff.

Nunca deshabilitar, silenciar o marcar como skip un test para obtener verde. Si la suite no
puede ejecutarse, la etapa queda bloqueada y se registra el comando exacto y el motivo.
