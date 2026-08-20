#!/bin/bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/scripts/harness-project.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $1"; exit 1; }
expect_exit() {
  expected="$1"
  shift
  set +e
  "$@" >/dev/null 2>&1
  actual=$?
  set -e
  [ "$actual" -eq "$expected" ] || fail "exit esperado $expected, recibido $actual: $*"
}

PROJECT="$TMP/project"
mkdir -p "$PROJECT/tests" "$PROJECT/scripts"
printf '# Demo project\n' > "$PROJECT/README.md"
printf '{"name":"manifest-name","scripts":{"build":"tool build","test":"tool test"}}\n' > "$PROJECT/package.json"
printf '#!/bin/sh\nexit 0\n' > "$PROJECT/scripts/health.sh"
chmod +x "$PROJECT/scripts/health.sh"
git -C "$PROJECT" init -q
git -C "$PROJECT" remote add origin 'https://token@example.test/team/demo.git'

(
  cd "$PROJECT"
  python3 "$CLI" identity init >/dev/null || fail "identity init debe funcionar"
  python3 "$CLI" context init >/dev/null || fail "context init debe funcionar"
)

PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" <<'PY'
import json
import sys
from pathlib import Path

from harness_context import context_fingerprint

root = Path(sys.argv[1]).resolve()
identity = json.loads((root / ".harness/project-identity.json").read_text(encoding="utf-8"))
assert identity["root"] == str(root)
assert identity["name"] == "manifest-name"
assert identity["remote"] == "https://example.test/team/demo"
before = context_fingerprint(root)
(root / "package.json").write_text(
    '{"name":"manifest-name","scripts":{"build":"tool build","test":"tool test --changed"}}\n',
    encoding="utf-8",
)
assert context_fingerprint(root) != before
PY

grep -Fq 'package.json' "$PROJECT/PROJECT-CONTEXT.md" || fail "contexto debe incluir manifest detectado"
grep -Fq 'tests' "$PROJECT/PROJECT-CONTEXT.md" || fail "contexto debe incluir directorio de tests"
grep -Fq 'Not detected; user/agent must verify' "$PROJECT/PROJECT-CONTEXT.md" \
  || fail "contexto debe marcar campos desconocidos"

before_check="$(cksum "$PROJECT/PROJECT-CONTEXT.md")"
stale="$(cd "$PROJECT" && python3 "$CLI" context check)" \
  || fail "context check debe informar stale sin fallar"
[ "$stale" = "stale" ] || fail "context check debe informar stale"
[ "$before_check" = "$(cksum "$PROJECT/PROJECT-CONTEXT.md")" ] \
  || fail "context check no debe reescribir el contexto"
(
  cd "$PROJECT"
  python3 "$CLI" context refresh >/dev/null || fail "context refresh debe funcionar"
)
fresh="$(cd "$PROJECT" && python3 "$CLI" context check)" \
  || fail "context check debe informar fresh sin fallar"
[ "$fresh" = "fresh" ] || fail "context check debe informar fresh"

cp "$PROJECT/PROJECT-CONTEXT.md" "$PROJECT/PROJECT-CONTEXT.backup"
printf '# malformed\n' > "$PROJECT/PROJECT-CONTEXT.md"
expect_exit 1 bash -c "cd '$PROJECT' && python3 '$CLI' context check"
mv "$PROJECT/PROJECT-CONTEXT.backup" "$PROJECT/PROJECT-CONTEXT.md"

OTHER="$TMP/other-project"
mkdir -p "$OTHER"
cp -R "$PROJECT/.harness" "$OTHER/.harness"
expect_exit 2 bash -c "cd '$OTHER' && python3 '$CLI' identity check"

git -C "$PROJECT" remote set-url origin 'ssh://git@example.test/team/other.git'
expect_exit 2 bash -c "cd '$PROJECT' && python3 '$CLI' identity check"

printf '{not json' > "$PROJECT/.harness/project-identity.json"
expect_exit 1 bash -c "cd '$PROJECT' && python3 '$CLI' identity check"

echo "ALL OK"
