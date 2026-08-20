# Plan: [nombre]

- **Estado:** [en progreso | pausado | completado]
- **Spec:** [ruta al documento de diseño]
- **Tarea actual:** ► Etapa [N], tarea [N.M]
- **Rama base:** develop
- **Rama de tarea:** codex/[descripcion]
- **Integracion:** PR rama de tarea -> develop; PR separado develop -> main/master
- **Complejidad:** [baja | media | alta] (T=[tareas], F=[archivos], S=[etapas], R=[riesgo], D=[duracion])
- **Modalidad recomendada:** [agente único | mixta | multi-agente] — [motivo]
- **Modalidad elegida:** [agente único | mixta | multi-agente]
- **Estimación agente único:** [rango de tokens]
- **Estimación multi-agente:** [rango de tokens]
- **Estimación mixta:** [rango de tokens]
- **Modelos por rol:** [orquestador/revisión | implementación | tareas mecánicas; auto o elegidos por el usuario]
- **Decisión de modelos:** [automático | un modelo para todo | modelo por agente]
- **Tokens por modelo/rol:** [rol -> modelo -> rango y supuestos]
- **Mapa de impacto:** [ruta o resumen de flujos, componentes, dependencias y datos afectados]
- **Preguntas abiertas:** [lista y estado; no iniciar implementación con preguntas materiales abiertas]
- **Estrategia de tests:** [unitarios | integración | E2E | no aplica, con comandos reales]
- **Cobertura objetivo:** [>=90% cambiado; 100% si es barato; exclusiones justificadas]
- **Estado de seguridad:** [pendiente | en revisión | verde | bloqueado]
- **Estado de regresión:** [pendiente | en revisión | verde | bloqueado]
- **Estado de handoff:** [pendiente | válido | bloqueado]

## Etapa 1: [nombre agrupador lógico]

**Objetivos (criterios de éxito):**
- [ ] [criterio medible, con evidencia esperada]

**Tareas:**
- [ ] 1.1 [tarea]
- [ ] 1.2 [tarea]

**Validación de etapa** (obligatoria antes de pasar a Etapa 2, ver skill stage-validator):
- [ ] Seguridad revisada (secretos, inputs, permisos, dependencias)
- [ ] Regresión: suite completa de tests en verde (pegar comando y resumen de salida)
- [ ] Objetivos cumplidos con evidencia

## Etapa 2: [nombre]

**Objetivos (criterios de éxito):**
- [ ] ...

**Tareas:**
- [ ] 2.1 ...

**Validación de etapa:**
- [ ] Seguridad | - [ ] Regresión | - [ ] Objetivos
