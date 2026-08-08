---
name: security-review
description: Usar antes de implementar cambios de riesgo y al cerrar cada etapa para revisar seguridad, datos, permisos y operaciones irreversibles.
---

# security-review

Este gate produce evidencia de seguridad; una afirmación de “se ve seguro” no lo cierra.

## Antes de implementar

Revisar el mapa de impacto y verificar:

- secretos y credenciales: no se agregan al repositorio ni a logs;
- inputs: validación, sanitización, límites y manejo de errores;
- autenticación, autorización, permisos y separación de tenants;
- datos: clasificación, exposición, retención, backups y migraciones;
- dependencias nuevas: origen, versión, mantenimiento y licencia;
- cambios destructivos: consumidores, entorno, rollback y confirmación explícita.

## Después de implementar

Inspeccionar el diff completo y ejecutar los checks de seguridad disponibles en el proyecto.
Registrar comandos, salida resumida, hallazgos y remediación en el plan. Si un check no
existe, registrar “no configurado” y describir la cobertura manual realizada.

## Gate

Bloquear la etapa si hay secreto expuesto, permiso injustificado, input sin validar,
migración irreversible sin rollback, dependencia no verificada o hallazgo crítico abierto.
Los riesgos aceptados requieren decisión explícita del usuario y quedan escritos.
