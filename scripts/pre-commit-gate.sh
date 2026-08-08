#!/bin/bash
# Hook PreToolUse(Bash): bloquea `git commit` si el health-check del proyecto falla.
# exit 0 = permitir; exit 2 = bloquear (stderr va a Claude). Falla abierto en errores propios.
set -u

cmd="$(python3 -c "
import json,sys
try:
    print(json.load(sys.stdin).get('tool_input',{}).get('command',''))
except Exception:
    print('')
" 2>/dev/null)" || exit 0

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

validate_execution_state() {
  [ -f ".harness/harness-state.py" ] || return 0
  [ -f "docs/plans/ACTIVE-PLAN.state.json" ] || return 0
  PYTHONDONTWRITEBYTECODE=1 python3 -B .harness/harness-state.py validate
}

current_branch() {
  git branch --show-current 2>/dev/null || true
}

is_protected_branch() {
  case "$1" in
    main|master|develop) return 0 ;;
    *) return 1 ;;
  esac
}

case "$cmd" in
  *"git commit"*)
    branch="$(current_branch)"
    if is_protected_branch "$branch"; then
      {
        echo "dev-harness bloqueó el commit: rama protegida '$branch'."
        echo "Crear una rama nueva desde develop para esta tarea."
      } >&2
      exit 2
    fi
    if [ -f ".harness/health.sh" ]; then
      if ! out="$(run_health 2>&1)"; then
        {
          echo "dev-harness bloqueó el commit: .harness/health.sh falla."
          echo "$out"
          echo "Arreglar el proyecto antes de commitear (prohibido commitear sobre proyecto roto)."
        } >&2
        exit 2
      fi
    fi
    if state_out="$(validate_execution_state 2>&1)"; then
      exit 0
    fi
    {
      echo "dev-harness bloqueó el commit: execution state inválido."
      echo "$state_out"
      echo "Reparar docs/plans/ACTIVE-PLAN.state.json antes de commitear."
    } >&2
    exit 2
    ;;
  *"git merge"*)
    branch="$(current_branch)"
    if is_protected_branch "$branch"; then
      {
        echo "dev-harness bloqueó el merge directo en rama protegida '$branch'."
        echo "Integrar mediante PR: tarea -> develop, luego develop -> main/master."
      } >&2
      exit 2
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac
