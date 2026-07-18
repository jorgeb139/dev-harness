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

case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

[ -f ".harness/health.sh" ] || exit 0

if out="$(run_health 2>&1)"; then
  exit 0
fi

{
  echo "dev-harness bloqueó el commit: .harness/health.sh falla."
  echo "$out"
  echo "Arreglar el proyecto antes de commitear (prohibido commitear sobre proyecto roto)."
} >&2
exit 2
