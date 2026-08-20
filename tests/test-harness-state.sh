#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/scripts/harness-state.py"
fail() { echo "FAIL: $1"; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/project/docs/plans" "$TMP/project/.harness"
printf '# Plan: demo\n' > "$TMP/project/docs/plans/ACTIVE-PLAN.md"
cat > "$TMP/project/.harness/plan.json" <<'JSON'
{
  "schema_version": 1,
  "plan_id": "demo",
  "original_scope": ["Exercise the state lifecycle"],
  "approved_scope": ["Exercise task transition gates"],
  "impact_analysis": {"forward": ["state CLI"], "risks": ["invalid transition"]},
  "mode_options": {
    "recommendation": "single-agent",
    "options": ["single-agent", "mixed", "multi-agent"],
    "estimates": {"single_agent": "25k-50k", "mixed": "45k-90k", "multi_agent": "80k-160k"}
  },
  "phases": [
    {
      "id": "1",
      "title": "State engine",
      "objectives": ["Complete task 1.1 with green reviews"],
      "tasks": [
        {
          "id": "1.1",
          "title": "Implement state engine",
          "status": "pending",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": [],
          "acceptance_criteria": ["State lifecycle remains valid"],
          "test_obligations": ["Run state tests"],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending"},
        "regression": {"status": "pending"},
        "tests": {"status": "pending"},
        "objectives": {"status": "pending"}
      }
    },
    {
      "id": "2",
      "title": "Planning integration",
      "objectives": ["Advance to task 2.1 only after dependency completion"],
      "tasks": [
        {
          "id": "2.1",
          "title": "Implement planning integration",
          "status": "pending",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": ["1.1"],
          "acceptance_criteria": ["Unknown task IDs fail closed"],
          "test_obligations": ["Run state tests"],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending"},
        "regression": {"status": "pending"},
        "tests": {"status": "pending"},
        "objectives": {"status": "pending"}
      }
    }
  ],
  "history": []
}
JSON
cd "$TMP/project"

python3 "$CLI" init \
  --plan-id demo \
  --plan-file .harness/plan.json \
  --branch codex/test \
  --owner tester \
  --phase 1 \
  --task 1.1 \
  --next-action "write the first failing test" >/dev/null \
  || fail "init debería crear el estado"

PYTHONPATH="$ROOT/scripts" python3 - "$TMP/project" <<'PY' \
  || { echo "FAIL: init debería adquirir el lock compartido"; exit 1; }
from contextlib import contextmanager
from pathlib import Path
import sys

import harness_state

root = Path(sys.argv[1])
state = root / "contract.state.json"
handoff = root / "contract.HANDOFF.md"
locked_paths = []

@contextmanager
def recording_lock(path):
    locked_paths.append(Path(path))
    yield

harness_state.locked = recording_lock
assert harness_state.main([
    "init",
    "--state-file", str(state),
    "--handoff-file", str(handoff),
    "--plan-id", "contract",
    "--plan-file", "docs/plans/ACTIVE-PLAN.md",
    "--branch", "codex/test",
    "--owner", "tester",
    "--phase", "1",
    "--task", "1.1",
    "--next-action", "verify lock",
]) == 0
assert locked_paths == [state]
PY

python3 "$CLI" show --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
assert d["status"] == "pending"
assert d["task"] == "1.1"
assert d["next_action"] == "write the first failing test"
assert d["history"][-1]["event"] == "initialized"
'
[ -f docs/plans/ACTIVE-PLAN.state.json ] || fail "falta state json"
[ -f docs/plans/ACTIVE-PLAN.HANDOFF.md ] || fail "falta handoff"

python3 "$CLI" start --task 1.1 --next-action "implement the state engine" >/dev/null \
  || fail "start debería funcionar"
python3 "$CLI" checkpoint \
  --commit abc123 \
  --test-command "bash tests/test-harness-state.sh" \
  --result "red expected" \
  --next-action "implement atomic writes" >/dev/null \
  || fail "checkpoint debería funcionar"

if python3 "$CLI" advance \
  --plan-json .harness/plan.json \
  --phase 2 \
  --task missing-task \
  --next-action "must fail" >/dev/null 2>&1; then
  fail "advance debería rechazar un task ID desconocido"
fi

if python3 "$CLI" advance \
  --plan-json .harness/plan.json \
  --phase 2 \
  --task 2.1 \
  --next-action "must fail" >/dev/null 2>&1; then
  fail "advance debería rechazar dependencias incompletas"
fi

python3 - <<'PY'
import json
from pathlib import Path

path = Path(".harness/plan.json")
plan = json.loads(path.read_text(encoding="utf-8"))
task = plan["phases"][0]["tasks"][0]
task["status"] = "completed"
task["evidence"] = {
    "implementation_checkpoint": {"status": "green", "commit": "abc123"},
    "regression": {"status": "green", "result": "ALL OK"},
    "tests": {"status": "green", "result": "ALL OK"},
}
path.write_text(json.dumps(plan), encoding="utf-8")
PY

if python3 "$CLI" advance \
  --plan-json .harness/plan.json \
  --phase 2 \
  --task 2.1 \
  --next-action "must fail" >/dev/null 2>&1; then
  fail "advance debería rechazar evidencia de revisión ausente"
fi

python3 "$CLI" show --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
assert d["phase"] == 1
assert d["task"] == "1.1"
assert d["status"] == "in_progress"
' || fail "advance rechazado no debería mutar el estado"

python3 - <<'PY'
import json
from pathlib import Path

path = Path(".harness/plan.json")
plan = json.loads(path.read_text(encoding="utf-8"))
plan["phases"][0]["tasks"][0]["evidence"]["security"] = {
    "status": "green",
    "result": "no findings",
}
path.write_text(json.dumps(plan), encoding="utf-8")
PY

python3 "$CLI" advance \
  --plan-json .harness/plan.json \
  --phase 2 \
  --task 2.1 \
  --next-action "implement planning-director" >/dev/null \
  || fail "advance debería funcionar"
python3 "$CLI" block --reason "waiting for design" --next-action "resume after approval" >/dev/null \
  || fail "block debería funcionar"
python3 "$CLI" resume --next-action "implement atomic writes" >/dev/null \
  || fail "resume debería funcionar"
python3 "$CLI" complete \
  --commit def456 \
  --test-command "bash tests/test-harness-state.sh" \
  --result "ALL OK" >/dev/null \
  || fail "complete debería funcionar"

python3 "$CLI" show --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
assert d["status"] == "completed"
assert d["last_verified_commit"] == "def456"
assert d["phase"] == 2
assert d["task"] == "2.1"
assert len(d["history"]) >= 6
'
python3 "$CLI" validate >/dev/null || fail "estado completado debería validar"

if python3 "$CLI" resume --next-action "must fail" >/dev/null 2>&1; then
  fail "resume no debería funcionar desde completed"
fi

echo "ALL OK"
