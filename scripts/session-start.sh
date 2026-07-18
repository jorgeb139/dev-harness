#!/bin/bash
# Hook SessionStart de dev-harness. stdout = contexto inyectado a la sesión.
# Falla abierto: siempre exit 0.
set -u

emit_rules() {
  cat <<'EOF'
[dev-harness activo] Reglas: (1) tarea compleja (3+ archivos, feature nueva o cambio
arquitectural) exige plan en docs/plans/ACTIVE-PLAN.md (skill plan-manager); (2) cerrar
etapa exige validación seguridad+regresión+objetivos con evidencia (skill stage-validator);
(3) regla 95%: sin certeza verificada, preguntar — prohibido inventar o suponer (skill
confidence-gate); (4) al ejecutar un plan, preguntar modalidad de agentes (skill
agent-orchestrator); (5) correcciones del usuario van a MUST-DO.md; (6) al cerrar plan,
correr skill retrospective.
EOF
}

main() {
  local has_output=0

  if [ -f ".harness/health.sh" ]; then
    has_output=1
    local health_out
    if health_out="$(bash .harness/health.sh 2>&1)"; then
      echo "HEALTH-CHECK: OK — proyecto levanta y tests base pasan."
    else
      echo "HEALTH-CHECK: FALLO — el proyecto está roto. Salida:"
      echo "$health_out"
      echo "REGLA: prohibido trabajar en features sobre proyecto roto. Primera tarea obligatoria: repararlo (con systematic-debugging) hasta que .harness/health.sh pase."
    fi
  fi

  if [ -f "docs/plans/ACTIVE-PLAN.md" ]; then
    has_output=1
    echo "PLAN ACTIVO (docs/plans/ACTIVE-PLAN.md):"
    grep -E "^# Plan:|Tarea actual" docs/plans/ACTIVE-PLAN.md | head -5
  fi

  if [ "$has_output" -eq 1 ]; then
    emit_rules
  fi
}

main 2>/dev/null || true
exit 0
