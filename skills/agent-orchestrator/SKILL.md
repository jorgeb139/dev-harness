---
name: agent-orchestrator
description: Usar al INICIAR la ejecución de un plan aprobado, antes de la primera tarea. Clasifica la complejidad, estima tokens, recomienda una modalidad de agentes y registra la decisión del usuario.
---

# agent-orchestrator

Antes de ejecutar la primera tarea de un plan aprobado, analizar el plan y presentar una
recomendación explícita. La recomendación no reemplaza la decisión del usuario: el usuario
puede aceptarla o elegir otra modalidad.

## Datos de complejidad

Extraer del plan, sin inventar datos faltantes:

- `T`: cantidad de tareas numeradas.
- `F`: cantidad estimada de archivos o módulos que se modificarán.
- `S`: cantidad de etapas.
- `R`: riesgo dominante: bajo, medio o alto. Alto incluye seguridad, datos, producción,
  migraciones, arquitectura o contratos públicos.
- `D`: duración estimada: corta (<1 hora), media (1-4 horas) o larga (>4 horas).

Si el plan no declara `F`, `R` o `D`, marcar el dato como supuesto y pedir confirmación
antes de ejecutar una tarea de riesgo medio o alto.

## Matriz de recomendación

Recomendar **agente único** si se cumplen todas estas condiciones: `T <= 2`, `F <= 3`,
`R = bajo`, `S = 1` y `D = corta`.

Recomendar **modalidad mixta** si el plan tiene complejidad media: `T` entre 3 y 5,
`F` entre 4 y 8, `R = medio`, o entre 2 y 3 etapas. Usar agente único para implementación
y subagente independiente solo para arquitectura, seguridad o revisión de alto impacto.

Recomendar **multi-agente** si se cumple cualquiera: `T > 5`, `F > 8`, `R = alto`,
`S > 3`, `D = larga`, o existen dos o más tareas independientes que pueden paralelizarse.

Si hay riesgo alto, la recomendación mínima es modalidad mixta aunque el plan sea pequeño.

## Estimación de tokens

Presentar siempre un rango, no una cifra falsa de precisión. Para `T` tareas y `S` etapas:

- **Agente único:** `T × 25k–50k` tokens.
- **Multi-agente:** `T × 60k–120k + S × 10k–20k` tokens.
- **Mixta:** calcular las tareas delegadas con `60k–120k` y las restantes con `25k–50k`,
  más `S × 10k–20k` de coordinación.

Los rangos incluyen lectura de contexto, implementación, revisión y validación. Son
estimaciones gruesas, no un presupuesto garantizado. Explicar qué variables las mueven:
cantidad de tareas, archivos, riesgo, reintentos y volumen de tests.

## Presentación obligatoria

Mostrar al usuario este resumen antes de la primera tarea:

```text
Complejidad: [baja|media|alta] (T=..., F=..., S=..., R=..., D=...)
Recomendación: [agente único|mixta|multi-agente]
Motivo: [dos frases concretas basadas en la matriz]
Estimación agente único: ... tokens
Estimación multi-agente: ... tokens
Estimación mixta: ... tokens
¿Aceptas la recomendación o eliges otra modalidad?
```

## Modalidades

### Multi-agente

- Un subagente fresco por tarea (implementador) + revisión independiente por tarea
  (revisor con contexto limpio) + validación de etapa por agente distinto al implementador.
- Modelos por defecto (ajustables por el usuario): arquitectura/revisión → modelo top
  (Opus o superior); implementación de tareas bien especificadas → modelo medio (Sonnet);
  tareas mecánicas (renombres, formateo, scaffolding) → modelo pequeño (Haiku).
- Costo: más tokens (cada subagente re-lee contexto). Beneficio: revisión cruzada real,
  contexto principal no se agota en sesiones largas.

### Agente único

- Todo en esta sesión, mismo modelo actual. Checkpoints de revisión con el usuario por etapa.
- Costo: menos tokens. Riesgo: sin revisión independiente; contexto largo degrada precisión.

### Mixta

- Agente único para tareas secuenciales y subagentes frescos para arquitectura, seguridad,
  investigación o revisión independiente.
- Es el default recomendado cuando hay riesgo medio pero no suficiente paralelismo para
  justificar multi-agente completo.

## Registro

Anotar al inicio de `ACTIVE-PLAN.md`:

- complejidad y datos `T/F/S/R/D`;
- modalidad recomendada y motivo;
- modalidad elegida por el usuario;
- estimado de cada modalidad;
- modelos por rol.

Respetar la decisión durante toda la ejecución salvo que el usuario la cambie explícitamente.
