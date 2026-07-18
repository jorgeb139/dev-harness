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

echo "ALL OK"
