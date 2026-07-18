---
name: stage-validator
description: Usar al terminar TODAS las tareas de una etapa de un plan activo, antes de iniciar la siguiente. Gate obligatorio de seguridad + regresión + objetivos con evidencia. Sin validación en verde escrita en el plan, la etapa no está cerrada.
---

# stage-validator

Correr las tres validaciones EN ORDEN y escribir el resultado en el bloque
"Validación de etapa" del plan. Si cualquiera falla: arreglar dentro de la etapa y repetir.
PROHIBIDO iniciar la etapa siguiente con validación pendiente o en rojo.

## 1. Seguridad

Revisar el diff completo de la etapa (`git diff <inicio-etapa>..HEAD`):
- Secretos: claves, tokens, contraseñas, URLs con credenciales en código o config commiteada.
- Inputs: todo dato externo (usuario, red, archivo) validado antes de usarse.
- Permisos: sin permisos de plataforma nuevos no justificados en el plan.
- Dependencias nuevas: nombre exacto verificado en el registro oficial (typosquatting),
  mantenida, licencia compatible.

## 2. Regresiones

- Correr la suite COMPLETA de tests del proyecto (no solo los nuevos) y
  `bash .harness/health.sh`. Pegar comando y resumen real de salida en el plan.
- Verificar que funcionalidad previa clave sigue operativa: identificar qué features
  existentes tocan los archivos modificados y ejercitarlas (test o ejecución manual).
- Cualquier test previamente verde ahora rojo = regresión: se arregla, jamás se
  deshabilita ni se marca skip para avanzar.

## 3. Objetivos de la etapa

Por cada criterio de éxito declarado en la etapa: marcar cumplido SOLO con evidencia
concreta (comando ejecutado + salida, test en verde, captura). "Debería funcionar" no es
evidencia. Si un objetivo no se cumplió: la etapa sigue abierta.

## Registro

Al pasar todo, escribir en el plan bajo la etapa:
`Validación: seguridad ✅ | regresión ✅ (comando: <cmd>) | objetivos ✅ — AAAA-MM-DD`
