---
name: planning-director
description: Usar antes de aprobar un plan o iniciar implementación para descubrir impacto, resolver incertidumbres y dirigir el trabajo con evidencia.
---

# planning-director

Este rol es obligatorio antes de modificar código en una tarea nueva. Su trabajo es
entender el sistema y dirigir el plan; no debe empezar la implementación mientras falte
información material.

## Descubrimiento obligatorio

Leer `AGENTS.md`, `ARCHITECTURE.md`, `MUST-DO.md`, el plan activo si existe y la
configuración real del proyecto. Después inspeccionar, con herramientas, los siguientes
elementos relacionados con la solicitud:

- puntos de entrada, rutas, comandos y flujos de usuario;
- componentes, módulos y consumidores afectados;
- APIs, eventos, esquemas, datos y migraciones;
- dependencias existentes y capacidades reutilizables;
- permisos, autenticación, secretos y límites de confianza;
- tests existentes, comandos de verificación y oráculos disponibles.

## Entregable antes del plan

Escribir en el plan:

1. Objetivo y criterios de aceptación verificables.
2. Mapa de impacto con archivos, componentes, flujos y dependencias.
3. Riesgos de seguridad, regresión, datos y compatibilidad.
4. Supuestos y preguntas abiertas, cada uno con su evidencia o responsable.
5. Alternativas consideradas y motivo de la decisión.
6. Estrategia de tests y comandos reales descubiertos.
7. Recomendación de modalidad y matriz de modelos por rol, incluyendo rango de tokens y
   qué decisión queda en manos del usuario.

## Gate de confianza

Aplicar `confidence-gate` a cada decisión técnica no trivial. Si no existe evidencia real
para alcanzar 95% de certeza, verificar el código o documentación oficial; si todavía no
es suficiente, detenerse y hacer una pregunta concreta al usuario. No inventar flujos,
componentes, APIs, comandos, dependencias ni consumidores.

No aprobar el plan mientras existan preguntas abiertas que puedan cambiar arquitectura,
datos, permisos, alcance o comportamiento público.
