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

case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

[ -f ".harness/health.sh" ] || exit 0

if out="$(bash .harness/health.sh 2>&1)"; then
  exit 0
fi

{
  echo "dev-harness bloqueó el commit: .harness/health.sh falla."
  echo "$out"
  echo "Arreglar el proyecto antes de commitear (prohibido commitear sobre proyecto roto)."
} >&2
exit 2
