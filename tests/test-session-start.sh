#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/scripts/session-start.sh"
fail() { echo "FAIL: $1"; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# Caso 1: proyecto sin harness -> silencio, exit 0
cd "$TMP"; out="$(bash "$S")" || fail "exit != 0 sin .harness"
[ -z "$out" ] || fail "debería callar sin .harness, dijo: $out"

# Caso 2: health.sh sano -> reporta sano
mkdir -p "$TMP/p2/.harness"; cd "$TMP/p2"
printf '#!/bin/bash\nexit 0\n' > .harness/health.sh
out="$(bash "$S")" || fail "exit != 0 con proyecto sano"
echo "$out" | grep -q "HEALTH-CHECK: OK" || fail "no reporta OK: $out"

# Caso 3: health.sh roto -> alerta y ordena reparar primero
mkdir -p "$TMP/p3/.harness"; cd "$TMP/p3"
printf '#!/bin/bash\necho build roto\nexit 1\n' > .harness/health.sh
out="$(bash "$S")" || fail "hook debe exit 0 incluso con proyecto roto"
echo "$out" | grep -q "HEALTH-CHECK: FALLO" || fail "no reporta fallo: $out"
echo "$out" | grep -q "build roto" || fail "no incluye salida del health: $out"
echo "$out" | grep -qi "repararlo" || fail "no ordena reparar: $out"

# Caso 4: plan activo -> incluye tarea actual
mkdir -p "$TMP/p4/docs/plans"; cd "$TMP/p4"
printf '# Plan: X\n- **Tarea actual:** ► Etapa 2, tarea 2.3\n' > docs/plans/ACTIVE-PLAN.md
out="$(bash "$S")" || fail "exit != 0 con plan"
echo "$out" | grep -q "Etapa 2, tarea 2.3" || fail "no inyecta tarea actual: $out"

echo "ALL OK"
