#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
S="$ROOT/scripts/pre-commit-gate.sh"
fail() { echo "FAIL: $1"; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
payload() { printf '{"tool_name":"Bash","tool_input":{"command":"%s"}}' "$1"; }

# Caso 1: comando sin git commit -> permite
cd "$TMP"; payload "ls -la" | bash "$S"
[ $? -eq 0 ] || fail "bloqueó comando inocente"

# Caso 2: git commit sin .harness en rama de tarea -> permite (proyecto sin harness)
mkdir -p "$TMP/p2"; cd "$TMP/p2"; git init -q; git checkout -q -b codex/test
payload "git commit -m x" | bash "$S"
[ $? -eq 0 ] || fail "bloqueó commit en rama de tarea sin harness"

# Caso 2b: git commit en develop -> bloquea
mkdir -p "$TMP/p2b"; cd "$TMP/p2b"; git init -q; git checkout -q -b develop
err="$(payload "git commit -m x" | bash "$S" 2>&1 >/dev/null)"; rc=$?
[ $rc -eq 2 ] || fail "esperaba exit 2 en develop, fue $rc"
echo "$err" | grep -q "rama protegida 'develop'" || fail "stderr sin rama protegida: $err"

# Caso 2c: git merge directo en main -> bloquea
mkdir -p "$TMP/p2c"; cd "$TMP/p2c"; git init -q; git checkout -q -b main
err="$(payload "git merge codex/test" | bash "$S" 2>&1 >/dev/null)"; rc=$?
[ $rc -eq 2 ] || fail "esperaba exit 2 en merge directo a main, fue $rc"
echo "$err" | grep -q "merge directo" || fail "stderr sin bloqueo de merge: $err"

# Caso 3: git commit con health roto -> bloquea con exit 2
mkdir -p "$TMP/p3/.harness"; cd "$TMP/p3"
printf '#!/bin/bash\necho tests rotos\nexit 1\n' > .harness/health.sh
err="$(payload "git commit -m x" | bash "$S" 2>&1 >/dev/null)"; rc=$?
[ $rc -eq 2 ] || fail "esperaba exit 2 con health roto, fue $rc"
echo "$err" | grep -q "tests rotos" || fail "stderr sin salida del health: $err"

# Caso 4: git commit con health sano -> permite
printf '#!/bin/bash\nexit 0\n' > .harness/health.sh
payload "git commit -m x" | bash "$S"
[ $? -eq 0 ] || fail "bloqueó commit con proyecto sano"

# Caso 5: plan activo con estado inválido -> bloquea commit
mkdir -p "$TMP/p5/.harness" "$TMP/p5/docs/plans"; cd "$TMP/p5"; git init -q; git checkout -q -b codex/test
cp "$ROOT/scripts/harness-state.py" .harness/harness-state.py
printf '{"status":"broken"}\n' > docs/plans/ACTIVE-PLAN.state.json
err="$(payload "git commit -m x" | bash "$S" 2>&1 >/dev/null)"; rc=$?
[ $rc -eq 2 ] || fail "esperaba exit 2 con estado inválido, fue $rc"
echo "$err" | grep -q "execution state" || fail "stderr sin bloqueo de estado: $err"

echo "ALL OK"
