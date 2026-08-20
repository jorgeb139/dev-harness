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
confidence-gate); (4) al ejecutar un plan, clasificar complejidad, recomendar modalidad y
mostrar estimados de tokens (skill agent-orchestrator); (5) branch-governance: rama nueva, develop obligatorio
como staging, PR tarea->develop y PR develop->main/master, sin aprobar/mergear salvo orden
explicita; (6) cambios destructivos requieren evidencia de impacto, rollback y confirmación
explicita (skill destructive-changes); (7) correcciones del usuario van a MUST-DO.md;
(8) decisiones estables van a ARCHITECTURE.md y contexto persistente a AGENTS.md;
(9) antes de planificar, planning-director debe analizar impacto y resolver preguntas;
(10) al cerrar una etapa, invocar security-review, regression-review, test-strategy y
checkpoint-handoff; (11) al iniciar un plan, agent-orchestrator clasifica complejidad,
recomienda modalidad y registra estimados de tokens; (12) al cerrar plan, correr skill
retrospective.
EOF
}

run_health() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c '
import subprocess, sys
try:
    p = subprocess.run(["bash", ".harness/health.sh"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
    sys.stdout.write(p.stdout)
    raise SystemExit(p.returncode)
except subprocess.TimeoutExpired as e:
    out = e.stdout or ""
    if isinstance(out, bytes):
        out = out.decode(errors="replace")
    sys.stdout.write(out)
    print("health-check excedio 60 segundos")
    raise SystemExit(124)
except Exception as e:
    print("dev-harness: no se pudo ejecutar health-check:", e)
    raise SystemExit(0)
'
    return $?
  fi

  bash .harness/health.sh
}

show_execution_state() {
  [ -f ".harness/harness-state.py" ] || return 1
  if [ -f ".harness/execution-state.json" ]; then
    echo "EXECUTION STATE (.harness/execution-state.json):"
  elif [ -f "docs/plans/ACTIVE-PLAN.state.json" ]; then
    echo "EXECUTION STATE (docs/plans/ACTIVE-PLAN.state.json):"
  else
    return 1
  fi
  local state_out
  if state_out="$(PYTHONDONTWRITEBYTECODE=1 python3 -B .harness/harness-state.py show 2>&1)"; then
    echo "$state_out"
  else
    echo "INVALID: $state_out"
    echo "REGLA: reparar el estado antes de continuar con la tarea activa."
  fi
  return 0
}

main() {
  local has_output=0

  if [ -f ".harness/health.sh" ]; then
    has_output=1
    local health_out
    if health_out="$(run_health 2>&1)"; then
      echo "HEALTH-CHECK: OK — proyecto levanta y tests base pasan."
    else
      echo "HEALTH-CHECK: FALLO — el proyecto esta roto. Salida:"
      echo "$health_out"
      echo "REGLA: prohibido trabajar en features sobre proyecto roto. Primera tarea obligatoria: repararlo (con systematic-debugging) hasta que .harness/health.sh pase."
    fi
  fi

  if [ -f "docs/plans/ACTIVE-PLAN.md" ]; then
    has_output=1
    echo "PLAN ACTIVO (docs/plans/ACTIVE-PLAN.md):"
    grep -E "^# Plan:|Tarea actual|Complejidad|Modalidad recomendada|Modalidad elegida|Estimación" docs/plans/ACTIVE-PLAN.md | head -12
  fi

  if show_execution_state; then
    has_output=1
  fi

  if [ "$has_output" -eq 1 ]; then
    emit_rules
  fi
}

main 2>/dev/null || true
exit 0
