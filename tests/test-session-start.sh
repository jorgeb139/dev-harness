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

# Caso 5: estado estructurado -> muestra handoff resumible
mkdir -p "$TMP/p5/docs/plans" "$TMP/p5/.harness"; cd "$TMP/p5"
cp "$ROOT/scripts/harness-state.py" .harness/harness-state.py
cp "$ROOT/scripts/harness_state.py" .harness/harness_state.py
cp "$ROOT/scripts/harness_store.py" .harness/harness_store.py
printf '# Plan: state\n' > docs/plans/ACTIVE-PLAN.md
PYTHONDONTWRITEBYTECODE=1 python3 -B .harness/harness-state.py init \
  --plan-id state --plan-file docs/plans/ACTIVE-PLAN.md --branch codex/test \
  --owner tester --phase 1 --task 1.1 --next-action "resume this exact action" >/dev/null
out="$(bash "$S")" || fail "exit != 0 con estado estructurado"
echo "$out" | grep -q "EXECUTION STATE" || fail "no reporta estado estructurado: $out"
echo "$out" | grep -q "resume this exact action" || fail "no reporta next action: $out"

# Caso 6: estado canónico sin mirror legacy -> usa el resolver canónico
rm docs/plans/ACTIVE-PLAN.state.json
out="$(bash "$S")" || fail "exit != 0 con estado canónico único"
echo "$out" | grep -q "EXECUTION STATE" \
  || fail "no reporta estado canónico único: $out"
echo "$out" | grep -q "resume this exact action" \
  || fail "no resuelve next action desde estado canónico: $out"

# Caso 7: proyecto inicializado con schema v1 -> migra al leer sin plan module
mkdir -p "$TMP/p7/docs/plans" "$TMP/p7/.harness"; cd "$TMP/p7"
cp "$ROOT/scripts/harness-state.py" .harness/harness-state.py
cp "$ROOT/scripts/harness_state.py" .harness/harness_state.py
cp "$ROOT/scripts/harness_store.py" .harness/harness_store.py
python3 - "$TMP/p5/.harness/execution-state.json" <<'PY'
import json
from pathlib import Path
import sys

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
state["schema_version"] = 1
for field in (
    "last_completed_task",
    "attempt_count",
    "attempt_metadata",
    "mode_decision",
    "selected_mode",
    "token_estimates",
    "checkpoint_metadata",
):
    state.pop(field)
Path("docs/plans/ACTIVE-PLAN.state.json").write_text(
    json.dumps(state), encoding="utf-8"
)
PY
out="$(bash "$S")" || fail "exit != 0 con estado schema v1"
echo "$out" | grep -q "EXECUTION STATE" || fail "no migra estado schema v1: $out"
echo "$out" | grep -q "resume this exact action" \
  || fail "no conserva next action de schema v1: $out"

# Caso 8: identidad cruzada -> no expone memoria del proyecto ajeno
mkdir -p "$TMP/p8/.harness" "$TMP/p8/docs/plans"; cd "$TMP/p8"
for f in harness-project.py harness_context.py harness_memory.py harness_store.py; do
  cp "$ROOT/scripts/$f" ".harness/$f"
done
PYTHONDONTWRITEBYTECODE=1 python3 -B .harness/harness-project.py identity init >/dev/null
python3 - <<'PY'
import json
from pathlib import Path
p = Path('.harness/project-identity.json')
d = json.loads(p.read_text())
d['root'] = '/tmp/another-project'
p.write_text(json.dumps(d))
Path('.harness/memory').mkdir()
Path('.harness/memory/memory.json').write_text('PRIVATE_FOREIGN_RULE')
PY
out="$(bash "$S")" || fail "identity mismatch debe seguir siendo fail-open del hook"
echo "$out" | grep -q "PROJECT IDENTITY: MISMATCH" || fail "no reporta mismatch de identidad: $out"
! echo "$out" | grep -q "PRIVATE_FOREIGN_RULE" || fail "expuso memoria de otro proyecto: $out"

echo "ALL OK"
