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
for t in AGENTS.md ARCHITECTURE.md MUST-DO.md PLAN-template.md HANDOFF-template.md CLAUDE.md health.sh PROJECT-CONTEXT.md MEMORY-README.md COMPLETION-POLICY.md; do
  [ -f "$ROOT/templates/$t" ] || fail "falta templates/$t"
done
grep -q "Tarea actual" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin marcador de tarea actual"
grep -q "Rama base" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin rama base"
grep -q "Integracion" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin integracion"
grep -q "Complejidad" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin complejidad"
grep -q "Modalidad recomendada" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin recomendacion"
grep -q "Estimación multi-agente" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin estimado multi-agente"
grep -q "Mapa de impacto" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin mapa de impacto"
grep -q "Estrategia de tests" "$ROOT/templates/PLAN-template.md" || fail "PLAN-template sin estrategia de tests"
grep -q "Branch governance" "$ROOT/templates/MUST-DO.md" || fail "MUST-DO sin branch governance"
grep -q "rollback" "$ROOT/templates/AGENTS.md" || fail "AGENTS sin compatibilidad segura"
grep -q "Memoria del proyecto" "$ROOT/templates/AGENTS.md" || fail "AGENTS sin memoria persistente documentada"
grep -q "modelos por rol" "$ROOT/templates/AGENTS.md" || fail "AGENTS sin selección de modelos"
grep -q "COMPLETION-POLICY" "$ROOT/commands/init.md" || fail "init.md sin política de completitud"
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
for ref in AGENTS.md ARCHITECTURE.md MUST-DO.md health.sh PLAN-template.md HANDOFF-template.md CLAUDE.md harness-state.py; do
  grep -q "$ref" "$ROOT/commands/init.md" || fail "init.md no referencia $ref"
done
ok "commands/init.md"

# --- Task 6+7+8: skills ---
for s in plan-manager confidence-gate stage-validator agent-orchestrator retrospective branch-governance destructive-changes planning-director security-review regression-review test-strategy checkpoint-handoff project-context project-memory; do
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
grep -q "Recomendación" "$ROOT/skills/agent-orchestrator/SKILL.md" || fail "agent-orchestrator sin recomendacion"
grep -q "T/F/S/R/D" "$ROOT/skills/agent-orchestrator/SKILL.md" || fail "agent-orchestrator sin variables de complejidad"
grep -q "modalidad mixta" "$ROOT/skills/agent-orchestrator/SKILL.md" || fail "agent-orchestrator sin modalidad mixta"
grep -q "Selección de modelos" "$ROOT/skills/agent-orchestrator/SKILL.md" || fail "agent-orchestrator sin selección de modelos"
grep -q -i "aprob" "$ROOT/skills/retrospective/SKILL.md" || fail "retrospective sin aprobación del usuario"
grep -q "develop" "$ROOT/skills/branch-governance/SKILL.md" || fail "branch-governance sin develop"
grep -q "main" "$ROOT/skills/branch-governance/SKILL.md" || fail "branch-governance sin main"
grep -q "master" "$ROOT/skills/branch-governance/SKILL.md" || fail "branch-governance sin master"
grep -q "PR" "$ROOT/skills/branch-governance/SKILL.md" || fail "branch-governance sin PR"
grep -q "confirmación explícita" "$ROOT/skills/destructive-changes/SKILL.md" || fail "destructive-changes sin confirmacion"
grep -q "branch-governance" "$ROOT/commands/init.md" || fail "init.md sin branch-governance"
grep -q "agent-orchestrator" "$ROOT/skills/plan-manager/SKILL.md" || fail "plan-manager sin agent-orchestrator"
grep -q "planning-director" "$ROOT/skills/plan-manager/SKILL.md" || fail "plan-manager sin planning-director"
grep -q "security-review" "$ROOT/skills/stage-validator/SKILL.md" || fail "stage-validator sin security-review"
grep -q "regression-review" "$ROOT/skills/stage-validator/SKILL.md" || fail "stage-validator sin regression-review"
grep -q "test-strategy" "$ROOT/skills/stage-validator/SKILL.md" || fail "stage-validator sin test-strategy"
grep -q "95%" "$ROOT/skills/planning-director/SKILL.md" || fail "planning-director sin gate 95"
grep -q -i "impacto" "$ROOT/skills/planning-director/SKILL.md" || fail "planning-director sin analisis de impacto"
grep -q -i "rollback" "$ROOT/skills/security-review/SKILL.md" || fail "security-review sin rollback"
grep -q -i "regres" "$ROOT/skills/regression-review/SKILL.md" || fail "regression-review sin regresion"
grep -q "90%" "$ROOT/skills/test-strategy/SKILL.md" || fail "test-strategy sin cobertura 90"
grep -q -i "E2E" "$ROOT/skills/test-strategy/SKILL.md" || fail "test-strategy sin E2E"
grep -q -i "checkpoint" "$ROOT/skills/checkpoint-handoff/SKILL.md" || fail "checkpoint-handoff sin checkpoint"
grep -q "last_verified_commit" "$ROOT/templates/HANDOFF-template.md" || fail "HANDOFF sin commit verificado"
ok "skills"


# --- Task 9: manifiesto Codex ---
[ -f "$ROOT/.codex-plugin/plugin.json" ] || fail "falta .codex-plugin/plugin.json"
python3 -c "
import json,re
from pathlib import Path
p=Path('$ROOT/.codex-plugin/plugin.json')
d=json.load(open(p))
allowed={'id','name','version','description','skills','apps','mcpServers','interface','author','homepage','repository','license','keywords'}
extra=set(d)-allowed
assert not extra, 'campos no aceptados: '+','.join(sorted(extra))
assert d['name']=='dev-harness'
assert re.match(r'^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:[-+][0-9A-Za-z.-]+)?$', d['version'])
assert d['skills']=='./skills/'
a=d['author']; assert a['name']=='Jorge'
i=d['interface']
for k in ['displayName','shortDescription','longDescription','developerName','category']:
    assert isinstance(i.get(k), str) and i[k].strip(), 'interface.'+k
assert isinstance(i.get('capabilities'), list) and all(isinstance(x,str) and x.strip() for x in i['capabilities'])
assert 'defaultPrompt' in i and isinstance(i['defaultPrompt'], list) and 1 <= len(i['defaultPrompt']) <= 3
assert re.match(r'^#[0-9A-Fa-f]{6}$', i.get('brandColor',''))
" || fail ".codex-plugin/plugin.json inválido"
ok "codex plugin.json"

# --- Task 10: compatibilidad Codex/Claude ---
grep -q "Codex" "$ROOT/README.md" || fail "README no documenta Codex"
grep -q "Claude Code" "$ROOT/README.md" || fail "README no documenta Claude Code"
! grep -R "CLAUDE_PLUGIN_ROOT" "$ROOT/skills" "$ROOT/commands" >/dev/null || fail "skills/commands dependen de CLAUDE_PLUGIN_ROOT"
grep -q "timeout=60" "$ROOT/scripts/session-start.sh" || fail "session-start sin timeout"
grep -q "recomendar modalidad" "$ROOT/scripts/session-start.sh" || fail "session-start sin recomendacion de modalidad"
grep -q "planning-director" "$ROOT/scripts/session-start.sh" || fail "session-start sin planning-director"
grep -q "checkpoint-handoff" "$ROOT/scripts/session-start.sh" || fail "session-start sin checkpoint-handoff"
grep -q "PROJECT IDENTITY" "$ROOT/scripts/session-start.sh" || fail "session-start sin identidad"
grep -q "timeout=60" "$ROOT/scripts/pre-commit-gate.sh" || fail "pre-commit sin timeout"
grep -q "rama protegida" "$ROOT/scripts/pre-commit-gate.sh" || fail "pre-commit no bloquea ramas protegidas"
grep -q "merge directo" "$ROOT/scripts/pre-commit-gate.sh" || fail "pre-commit no bloquea merge directo"
[ -x "$ROOT/scripts/install-codex-skills.sh" ] || fail "install-codex-skills.sh no executable"
bash -n "$ROOT/scripts/install-codex-skills.sh" || fail "install-codex-skills.sh con error de sintaxis"
grep -q "~/.agents/skills/dev-harness" "$ROOT/README.md" || fail "README no documenta symlink Codex"
grep -q '"version": "0.4.0"' "$ROOT/.claude-plugin/plugin.json" || fail "plugin Claude sin version 0.4.0"
grep -q '"version": "0.4.0"' "$ROOT/.codex-plugin/plugin.json" || fail "plugin Codex sin version 0.4.0"
ok "compatibilidad dual"

echo "ALL OK"
