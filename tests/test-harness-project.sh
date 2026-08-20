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

always_output="$(cd "$PROJECT" && python3 "$CLI" memory always \
  --text "Use focused tests before changing behavior")" \
  || fail "memory always debe funcionar"
always_id="$(printf '%s\n' "$always_output" | sed -n 's/^MEMORY UPDATED: //p')"
[ -n "$always_id" ] || fail "memory always debe notificar el ID de la regla"

PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" "$always_id" <<'PY'
import sys
from pathlib import Path

from harness_memory import load_memory

memory = load_memory(Path(sys.argv[1]))
entry = next(entry for entry in memory["entries"] if entry["id"] == sys.argv[2])
assert entry["rule"] == "Use focused tests before changing behavior"
assert entry["scope"] == "project"
assert entry["source"] == "explicit_always"
assert entry["occurrences"] == 1
assert entry["confidence"] == "high"
assert entry["status"] == "active"
assert entry["project_identity"] == memory["project_identity"]
assert entry["notification"] == f"MEMORY UPDATED: {entry['id']}"
PY

PYTHONPATH="$ROOT/scripts" python3 - <<'PY'
from harness_memory import precedence

assert precedence() == [
    "current explicit user instruction",
    "explicit project rule",
    "learned project memory",
    "AGENTS.md / CLAUDE.md rules",
    "general harness skills",
    "agent defaults",
]
PY

first_correction="$(cd "$PROJECT" && python3 "$CLI" memory correction \
  --text "Por favor, siempre usa nombres descriptivos en las pruebas")" \
  || fail "la primera corrección debe funcionar"
correction_id="$(printf '%s\n' "$first_correction" | sed -n 's/^MEMORY CANDIDATE: //p')"
[ -n "$correction_id" ] || fail "la primera corrección debe quedar como candidata"

second_correction="$(cd "$PROJECT" && python3 "$CLI" memory correction \
  --text "usa nombres descriptivos en las pruebas")" \
  || fail "la segunda corrección equivalente debe funcionar"
[ "$second_correction" = "MEMORY UPDATED: $correction_id" ] \
  || fail "la segunda corrección debe promover y notificar la misma regla"

PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" "$correction_id" <<'PY'
import sys
from pathlib import Path

from harness_memory import load_memory

memory = load_memory(Path(sys.argv[1]))
entry = next(entry for entry in memory["entries"] if entry["id"] == sys.argv[2])
assert entry["source"] == "repeated_correction"
assert entry["occurrences"] == 2
assert entry["confidence"] == "high"
assert entry["status"] == "active"
assert entry["notification"] == f"MEMORY UPDATED: {entry['id']}"
PY

uncertain_output="$(cd "$PROJECT" && python3 "$CLI" memory correction \
  --text "Agrupa las aserciones por flujo de usuario")" \
  || fail "la corrección incierta debe funcionar"
uncertain_id="$(printf '%s\n' "$uncertain_output" | sed -n 's/^MEMORY CANDIDATE: //p')"
[ -n "$uncertain_id" ] || fail "la corrección incierta debe quedar como candidata"

PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" "$uncertain_id" <<'PY'
import sys
from pathlib import Path

from harness_memory import load_memory

memory = load_memory(Path(sys.argv[1]))
entry = next(entry for entry in memory["entries"] if entry["id"] == sys.argv[2])
assert entry["occurrences"] == 1
assert entry["confidence"] == "candidate"
assert entry["status"] == "candidate"
assert "notification" not in entry
PY

SENSITIVE_INPUT='api_key=not-a-real-secret'
set +e
sensitive_output="$(cd "$PROJECT" && python3 "$CLI" memory always --text "$SENSITIVE_INPUT" 2>&1)"
sensitive_exit=$?
set -e
[ "$sensitive_exit" -eq 1 ] || fail "memory always debe rechazar secretos"
case "$sensitive_output" in
  *"$SENSITIVE_INPUT"*) fail "el secreto rechazado no debe imprimirse" ;;
esac
if grep -R -Fq 'not-a-real-secret' "$PROJECT/.harness/memory" 2>/dev/null; then
  fail "los secretos no deben persistirse en memoria"
fi

memory_list="$(cd "$PROJECT" && python3 "$CLI" memory list)" \
  || fail "memory list debe funcionar"
printf '%s\n' "$memory_list" | python3 -c '
import json, sys
value = json.load(sys.stdin)
assert len(value["entries"]) == 3
'

for field in source supersedes notification; do
  PROJECT="$PROJECT" FIELD="$field" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["PROJECT"]) / ".harness/memory/memory.json"
memory = json.loads(path.read_text(encoding="utf-8"))
entry = memory["entries"][0]
entry["source"] = "explicit_always"
entry.pop("supersedes", None)
entry.pop("notification", None)
entry[os.environ["FIELD"]] = f"api_key=stored-{os.environ['FIELD']}-secret"
path.write_text(json.dumps(memory), encoding="utf-8")
PY
  SENSITIVE_METADATA="api_key=stored-$field-secret"
  set +e
  metadata_output="$(cd "$PROJECT" && python3 "$CLI" memory list 2>&1)"
  metadata_exit=$?
  set -e
  [ "$metadata_exit" -eq 1 ] || fail "memory list debe rechazar $field sensible"
  case "$metadata_output" in
    *"$SENSITIVE_METADATA"*) fail "memory list no debe imprimir $field sensible" ;;
  esac
done

cp "$PROJECT/PROJECT-CONTEXT.md" "$PROJECT/PROJECT-CONTEXT.backup"
printf '# malformed\n' > "$PROJECT/PROJECT-CONTEXT.md"
expect_exit 1 bash -c "cd '$PROJECT' && python3 '$CLI' context check"
mv "$PROJECT/PROJECT-CONTEXT.backup" "$PROJECT/PROJECT-CONTEXT.md"

OTHER="$TMP/other-project"
mkdir -p "$OTHER"
cp -R "$PROJECT/.harness" "$OTHER/.harness"
expect_exit 2 bash -c "cd '$OTHER' && python3 '$CLI' identity check"
expect_exit 2 bash -c "cd '$OTHER' && python3 '$CLI' memory list"
expect_exit 2 bash -c "cd '$OTHER' && python3 '$CLI' memory always --text 'safe rule'"
expect_exit 2 bash -c "cd '$OTHER' && python3 '$CLI' memory correction --text 'safe correction'"
PYTHONPATH="$ROOT/scripts" python3 - "$OTHER" <<'PY'
import sys
from pathlib import Path

from harness_memory import load_memory

try:
    load_memory(Path(sys.argv[1]))
except ValueError as exc:
    assert "identity mismatch" in str(exc)
else:
    raise AssertionError("cross-project memory must be rejected")
PY

git -C "$PROJECT" remote set-url origin 'ssh://git@example.test/team/other.git'
expect_exit 2 bash -c "cd '$PROJECT' && python3 '$CLI' identity check"

printf '{not json' > "$PROJECT/.harness/project-identity.json"
expect_exit 1 bash -c "cd '$PROJECT' && python3 '$CLI' identity check"

echo "ALL OK"
