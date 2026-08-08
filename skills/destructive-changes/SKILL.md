---
name: destructive-changes
description: Usar antes de eliminar datos, APIs, configuraciones, permisos, archivos o introducir cambios irreversibles.
---

# destructive-changes

Esta skill complementa `confidence-gate`. Su objetivo es impedir que la regla de
simplicidad se convierta en autorización implícita para destruir estado.

## Activar el gate

Detenerse antes de:

- borrar o transformar tablas, columnas, buckets, archivos o datos persistentes;
- eliminar APIs, eventos, configuraciones o comportamientos usados por consumidores;
- cambiar permisos, autenticación, políticas de acceso o secretos;
- ejecutar comandos irreversibles o introducir una migración sin rollback probado.

## Evidencia mínima

Antes de continuar, verificar en código, configuración y documentación:

1. Qué consumidores y datos están afectados.
2. Si el entorno es local, staging o producción.
3. Qué backup, migración reversible o rollback existe y cómo se probará.
4. Qué alternativa no destructiva satisface la necesidad actual.

## Confirmación

Si hay datos, contratos públicos o producción involucrados, pedir confirmación explícita
al usuario con el alcance exacto. No interpretar "simplifica", "limpia" o "elimina lo
obsoleto" como autorización para borrar estado.
