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
agent-orchestrator); (5) branch-governance: rama nueva por tarea, develop obligatorio
como staging, PR tarea->develop y PR develop->main/master, sin aprobar/mergear salvo orden
explicita; (6) correcciones del usuario van a MUST-DO.md; (7) al cerrar plan, correr skill
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
    grep -E "^# Plan:|Tarea actual" docs/plans/ACTIVE-PLAN.md | head -5
  fi

  if [ "$has_output" -eq 1 ]; then
    emit_rules
  fi
}

main 2>/dev/null || true
exit 0
