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
