# Completion Policy

Una tarea termina solo cuando su implementación tiene commit verificable, criterios de
aceptación cumplidos, evidencia de seguridad, regresión y tests, y handoff actualizado.
El revisor confirma que se respetó el scope y que no se inventaron requisitos.

Una etapa termina cuando todas sus tareas están completas y sus gates de seguridad,
regresión, estrategia de tests, objetivos y handoff están en verde en el plan JSON.

Un plan termina cuando todas las etapas están completas, no hay blockers, la cobertura
del código modificado es al menos 90% (100% si es barato y significativo), las pruebas
de integración/E2E aplicables pasan, existe retrospectiva y el archivado escribe el
Markdown, JSON, estado, handoff e índice de evidencia sin conservar conversación ni
razonamiento interno.
