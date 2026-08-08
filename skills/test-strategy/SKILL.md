---
name: test-strategy
description: Usar durante la planificación y validación para elegir capas de tests, descubrir comandos reales y aplicar cobertura proporcional al coste.
---

# test-strategy

## Selección por arquitectura

- **Unitarios:** obligatorios para lógica nueva o modificada y casos de error relevantes.
- **Integración:** obligatorios cuando hay límites reales entre módulos, base de datos,
  filesystem, colas, APIs o servicios externos.
- **E2E:** obligatorios para los journeys críticos cuando existe UI, API pública o flujo
  completo desplegable. No exigir E2E artificial para documentación, configuración o una
  librería aislada sin flujo de usuario.

Descubrir el framework, package manager y comandos leyendo la configuración del proyecto;
no inventar `npm`, `pytest`, `go test` ni ningún runner.

## Cobertura

La cobertura mínima objetivo es 90% del código de producción nuevo o modificado. Medir
statements, líneas, funciones y branches si la herramienta real lo permite. Subir a 100%
solo si el coste marginal es bajo y los tests validan comportamiento, no detalles internos.

Si alcanzar 90% exige tests frágiles, documentar el riesgo y preguntar antes de continuar.
Registrar porcentaje, comando, alcance y líneas excluidas; la cobertura no reemplaza tests
de comportamiento, integración, seguridad o E2E.

## Entregable

El plan debe declarar capas aplicables, comando exacto, umbral, evidencia esperada y
criterio explícito de “no aplica” para cada capa omitida.
