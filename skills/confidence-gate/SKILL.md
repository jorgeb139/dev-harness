---
name: confidence-gate
description: Usar ante CUALQUIER decisión técnica no trivial durante diseño o implementación. Regla 95% — si no hay 95% de certeza verificada sobre cómo hacer algo, prohibido continuar; verificar contra fuentes reales o preguntar al usuario. Prohibido inventar o suponer.
---

# confidence-gate

## Regla 95%

Antes de cada decisión técnica no trivial (elegir API, asumir comportamiento de librería,
estructura de datos externa, comando de build, esquema de config), autoevaluar: ¿tengo 95%
de certeza de que esto es correcto Y de cómo hacerlo?

- **Sí, por verificación:** lo comprobé en esta sesión contra código real, salida de
  comandos, o documentación oficial. Continuar y citar la evidencia.
- **No:** PROHIBIDO continuar. En orden: (1) verificar con herramientas (leer el código
  fuente, correr el comando, leer docs oficiales); (2) si la verificación no resuelve, o la
  decisión depende de preferencias del usuario: preguntar, una pregunta por mensaje, con
  opciones y recomendación.

## Prohibiciones absolutas

- Inventar nombres de APIs, funciones, flags, paquetes o versiones sin verificarlos.
- Suponer que un archivo, símbolo o comportamiento existe sin haberlo leído/ejecutado.
- Rellenar huecos de un requisito ambiguo con una interpretación propia sin marcarla y
  preguntar.
- Presentar como hecho lo que es hipótesis. Hipótesis se declara como hipótesis.

## Señales de que estás violando la regla

"Probablemente la API acepta...", "normalmente esto funciona así...", "asumo que...",
"debería existir un método...". Cada una de esas frases exige: verificar o preguntar.
