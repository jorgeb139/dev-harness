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

# Caso 2: git commit sin .harness -> permite (proyecto sin harness)
payload "git commit -m x" | bash "$S"
[ $? -eq 0 ] || fail "bloqueó commit en proyecto sin harness"

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

echo "ALL OK"
