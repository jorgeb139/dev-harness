# AGENTS.md — criterio de ingeniería del proyecto

Estas reglas son defaults de diseño. Si una regla entra en conflicto con seguridad,
datos, contratos públicos o una instrucción explícita del usuario, detenerse y pedir
confirmación antes de continuar.

## Implementación

1. Elige la implementación más simple que resuelva la necesidad actual. No agregues
   abstracciones, configuración o capas para necesidades hipotéticas.
2. Construye primero un flujo vertical mínimo de extremo a extremo. Después separa
   responsabilidades en módulos cuando exista complejidad real.
3. Mantén componentes modulares y con una sola responsabilidad, con el nivel de
   separación proporcional al tamaño del problema.
4. Antes de añadir código o paquetes, revisa qué ofrecen las dependencias y utilidades
   ya existentes. Una dependencia nueva requiere justificar su necesidad y mantenimiento.
5. Usa bibliotecas maduras y patrones probados cuando encajen; no reescribas capacidades
   existentes sin una razón concreta y verificada.

## Compatibilidad y evolución

6. No mantengas compatibilidad por reflejo, pero tampoco elimines APIs, configuraciones,
   tablas, datos o comportamientos existentes sin identificar consumidores, impacto y
   rollback. Los cambios destructivos requieren confirmación explícita.
7. Diseña decisiones que no bloqueen la evolución futura, sin implementar infraestructura
   especulativa. Documenta decisiones arquitectónicas duraderas en ARCHITECTURE.md.

## Memoria del proyecto

Antes de modificar código, lee `AGENTS.md`, `ARCHITECTURE.md`, `MUST-DO.md` y, si existe,
`docs/plans/ACTIVE-PLAN.md`. Estos archivos son la memoria persistente del proyecto.
Registra decisiones estables en `ARCHITECTURE.md`, reglas aprobadas en `MUST-DO.md` y
trabajo en curso en el plan. No trates el contexto de una sesión anterior como memoria
confiable si no quedó escrito en esos archivos o en Git.

La identidad y el contexto generado viven en `.harness/project-identity.json` y
`PROJECT-CONTEXT.md`. La memoria aprendida vive en `.harness/memory/`; solo se carga
después de validar que la identidad local coincide. El origen operativo del plan es
`.harness/plan.json` y el estado recuperable es `.harness/execution-state.json`; el
`ACTIVE-PLAN.md` es una proyección generada y no debe editarse directamente.

## Orquestación y calidad

El primer rol es el orquestador: inspecciona antes de actuar, alcanza al menos 95% de
certeza con evidencia o preguntas, recorre dependencias hacia atrás y hacia adelante,
evalúa happy paths y sad paths, y confirma el scope sin inventar requisitos. Presenta
agente único, modalidad mixta y multi-agente con riesgos, operación y tokens estimados.
También presenta modelos por rol y tokens por modelo: automático, un modelo elegido para
todo, o una selección por agente. El usuario decide tanto la modalidad como los modelos.

Cada tarea pasa por implementador y revisor de seguridad/regresión/tests. La tarea no se
cierra hasta que el loop de corrección sea verde, con cobertura mínima de 90% del código
modificado y 100% solo cuando el coste marginal sea bajo; integración y E2E se ejecutan
cuando la arquitectura los haga aplicables.
