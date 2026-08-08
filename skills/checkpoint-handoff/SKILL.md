---
name: checkpoint-handoff
description: Usar después de cada tarea, antes de compactar o terminar sesión y al bloquearse para persistir estado recuperable por otro agente.
---

# checkpoint-handoff

El checkpoint es la memoria operativa. No confiar en el contexto conversacional para
transferir trabajo entre agentes o sesiones.

## Cuándo escribirlo

- al iniciar y terminar cada tarea;
- después de cada validación importante;
- antes de compactar, cerrar la sesión o cambiar de agente;
- inmediatamente al quedar bloqueado.

## Contenido obligatorio

Actualizar el state engine y el handoff con:

- plan, etapa, tarea y owner;
- estado válido y último commit verificado;
- archivos y decisiones modificados;
- tests ejecutados, comando y resultado real;
- intentos fallidos y por qué no funcionaron;
- bloqueos y pregunta pendiente;
- siguiente acción exacta, ejecutable por otro agente.

Un handoff sin siguiente acción, evidencia o commit verificable está incompleto y no cierra
la tarea. Usar `scripts/harness-state.py` para evitar ediciones parciales del JSON.
