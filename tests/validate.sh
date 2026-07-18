#!/bin/bash
# Validador del plugin dev-harness. exit 0 = OK, exit 1 = FAIL.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

# --- Task 1: manifiestos ---
[ -f "$ROOT/.claude-plugin/plugin.json" ] || fail "falta .claude-plugin/plugin.json"
python3 -c "
import json,sys
d=json.load(open('$ROOT/.claude-plugin/plugin.json'))
assert d['name']=='dev-harness', 'plugin name debe ser dev-harness'
assert 'description' in d and 'version' in d
" || fail "plugin.json inválido"
ok "plugin.json"

[ -f "$ROOT/.claude-plugin/marketplace.json" ] || fail "falta marketplace.json"
python3 -c "
import json
d=json.load(open('$ROOT/.claude-plugin/marketplace.json'))
assert d['name']=='dev-harness-marketplace'
assert any(p['name']=='dev-harness' for p in d['plugins'])
" || fail "marketplace.json inválido"
ok "marketplace.json"

[ -f "$ROOT/README.md" ] || fail "falta README.md"
ok "README.md"

# --- Task 2: templates ---
for t in ARCHITECTURE.md MUST-DO.md PLAN-template.md health.sh; do
  [ -f "$ROOT/templates/$t" ] || fail "falta templates/$t"
done
grep -q "Tarea actual" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin marcador de tarea actual"
grep -q "Validación de etapa" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin sección de validación"
bash -n "$ROOT/templates/health.sh" || fail "templates/health.sh con error de sintaxis"
ok "templates"

# --- Task 3: hook session-start ---
bash "$ROOT/tests/test-session-start.sh" || fail "test-session-start"
ok "session-start.sh"

# --- Task 4: hook pre-commit-gate + hooks.json ---
bash "$ROOT/tests/test-pre-commit-gate.sh" || fail "test-pre-commit-gate"
python3 -c "
import json
d=json.load(open('$ROOT/hooks/hooks.json'))
h=d['hooks']
assert 'SessionStart' in h and 'PreToolUse' in h
flat=json.dumps(d)
assert 'session-start.sh' in flat and 'pre-commit-gate.sh' in flat
assert 'CLAUDE_PLUGIN_ROOT' in flat
" || fail "hooks.json inválido"
ok "pre-commit-gate.sh + hooks.json"

# --- Task 5: comando init ---
[ -f "$ROOT/commands/init.md" ] || fail "falta commands/init.md"
for ref in ARCHITECTURE.md MUST-DO.md health.sh PLAN-template.md; do
  grep -q "$ref" "$ROOT/commands/init.md" || fail "init.md no referencia $ref"
done
ok "commands/init.md"

echo "ALL OK"
