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

# --- Task 6+7+8: skills ---
for s in plan-manager confidence-gate stage-validator agent-orchestrator retrospective; do
  f="$ROOT/skills/$s/SKILL.md"
  [ -f "$f" ] || fail "falta skills/$s/SKILL.md"
  head -1 "$f" | grep -q -- "---" || fail "skills/$s sin frontmatter"
  grep -q "^name: $s" "$f" || fail "skills/$s frontmatter name incorrecto"
  grep -q "^description:" "$f" || fail "skills/$s sin description"
done
grep -q "95" "$ROOT/skills/confidence-gate/SKILL.md" || fail "confidence-gate sin regla 95"
grep -q "ACTIVE-PLAN.md" "$ROOT/skills/plan-manager/SKILL.md" || fail "plan-manager sin ruta de plan"
grep -q -i "regresi" "$ROOT/skills/stage-validator/SKILL.md" || fail "stage-validator sin regresión"
grep -q -i "token" "$ROOT/skills/agent-orchestrator/SKILL.md" || fail "agent-orchestrator sin estimado tokens"
grep -q -i "aprob" "$ROOT/skills/retrospective/SKILL.md" || fail "retrospective sin aprobación del usuario"
ok "skills"

echo "ALL OK"
