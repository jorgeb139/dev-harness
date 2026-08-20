---
name: project-memory
description: Gestiona memoria de proyecto aislada, promoción de reglas y notificaciones.
---

# project-memory

Validar identidad antes de leer o escribir `.harness/memory/`. Persistir solo reglas,
decisiones y metadatos mínimos; nunca conversaciones, tokens, secretos ni razonamiento.

Una instrucción explícita de "siempre" se activa de inmediato. La misma corrección exacta
repetida más de una vez se promueve automáticamente, sin pedir aprobación, y se notifica.
Una coincidencia ambigua queda como `candidate`. Las propuestas que cambian el harness
general requieren aprobación explícita. Precedencia: usuario actual, reglas activas del
proyecto, `AGENTS.md`, contexto generado, defaults del harness.
