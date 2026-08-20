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
    "estimates": {"single-agent": "25k-50k", "mixed": "45k-90k", "multi-agent": "80k-160k"}
  },
  "phases": [
    {
      "id": "1",
      "title": "State engine",
      "objectives": [
        {
          "description": "Complete task 1.1 with green reviews",
          "status": "pending",
          "evidence": null
        }
      ],
      "tasks": [
        {
          "id": "1.1",
          "title": "Implement state engine",
          "status": "pending",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": [],
          "acceptance_criteria": [
            {
              "description": "State lifecycle remains valid",
              "status": "pending",
              "evidence": null
            }
          ],
          "test_obligations": [
            {
              "description": "Run state tests",
              "status": "pending",
              "command": "bash tests/test-harness-state.sh",
              "evidence": null
            }
          ],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending", "evidence": "queued"},
        "regression": {"status": "pending", "evidence": "queued"},
        "tests": {"status": "pending", "evidence": "queued"},
        "objectives": {"status": "pending", "evidence": "queued"}
      }
    },
    {
      "id": "2",
      "title": "Planning integration",
      "objectives": [
        {
          "description": "Advance to task 2.1 only after dependency completion",
          "status": "pending",
          "evidence": null
        }
      ],
      "tasks": [
        {
          "id": "2.1",
          "title": "Implement planning integration",
          "status": "pending",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": ["1.1"],
          "acceptance_criteria": [
            {
              "description": "Unknown task IDs fail closed",
              "status": "pending",
              "evidence": null
            }
          ],
          "test_obligations": [
            {
              "description": "Run state tests",
              "status": "pending",
              "command": "bash tests/test-harness-state.sh",
              "evidence": null
            }
          ],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending", "evidence": "queued"},
        "regression": {"status": "pending", "evidence": "queued"},
        "tests": {"status": "pending", "evidence": "queued"},
        "objectives": {"status": "pending", "evidence": "queued"}
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
  || { echo "FAIL: resolución canónica de estado"; exit 1; }
import json
from pathlib import Path
import sys

from harness_state import resolve_execution_state, validate_state

root = Path(sys.argv[1]).resolve()
resolution = resolve_execution_state(root)
canonical = root / ".harness/execution-state.json"
legacy = root / "docs/plans/ACTIVE-PLAN.state.json"
assert resolution.path == canonical
assert resolution.write_paths == (canonical, legacy)
canonical_value = json.loads(canonical.read_text(encoding="utf-8"))
legacy_value = json.loads(legacy.read_text(encoding="utf-8"))
assert canonical_value == legacy_value
validate_state(canonical_value)
assert canonical_value["schema_version"] == 2
assert canonical_value["last_completed_task"] is None
assert canonical_value["attempt_count"] == 0
assert canonical_value["attempt_metadata"] == []
assert canonical_value["selected_mode"] is None
assert canonical_value["token_estimates"] == {}
assert canonical_value["checkpoint_metadata"] is None

legacy_value["next_action"] = "divergent pointer"
legacy.write_text(json.dumps(legacy_value), encoding="utf-8")
try:
    resolve_execution_state(root)
except ValueError as exc:
    assert "diverge" in str(exc)
else:
    raise AssertionError("divergent canonical and legacy states must fail closed")
legacy.write_text(json.dumps(canonical_value), encoding="utf-8")
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
[ -f .harness/execution-state.json ] || fail "falta estado canónico"
[ -f docs/plans/ACTIVE-PLAN.HANDOFF.md ] || fail "falta handoff"
grep -Fq 'GENERATED FILE' docs/plans/ACTIVE-PLAN.md \
  || fail "init debería regenerar la proyección canónica"

python3 "$CLI" start --task 1.1 --next-action "implement the state engine" >/dev/null \
  || fail "start debería funcionar"
grep -Fq '**Execution status:** `in_progress`' docs/plans/ACTIVE-PLAN.md \
  || fail "start debería regenerar estado de ejecución"
grep -Fq 'implement the state engine' docs/plans/ACTIVE-PLAN.md \
  || fail "start debería proyectar next_action"
python3 "$CLI" checkpoint \
  --commit abc123 \
  --test-command "bash tests/test-harness-state.sh" \
  --result "red expected" \
  --next-action "implement atomic writes" >/dev/null \
  || fail "checkpoint debería funcionar"
python3 "$CLI" show --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
assert d["checkpoint_metadata"]["commit"] == "abc123"
assert d["checkpoint_metadata"]["test_command"] == "bash tests/test-harness-state.sh"
assert d["checkpoint_metadata"]["result"] == "red expected"
' || fail "checkpoint debería persistir metadata tipada"
grep -Fq 'abc123' docs/plans/ACTIVE-PLAN.md \
  || fail "checkpoint debería regenerar su metadata"

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
    "implementation_checkpoint": {
        "status": "green",
        "commit": "abc123",
        "test_command": "bash tests/test-harness-state.sh",
        "result": "ALL OK",
    },
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
cmp -s .harness/execution-state.json docs/plans/ACTIVE-PLAN.state.json \
  || fail "advance debería sincronizar estado canónico y legacy"
grep -Fq '**Current task:** ► Phase 2, task 2.1' docs/plans/ACTIVE-PLAN.md \
  || fail "advance debería regenerar el marcador de tarea"
python3 "$CLI" block --reason "waiting for design" --next-action "resume after approval" >/dev/null \
  || fail "block debería funcionar"
grep -Fq 'waiting for design' docs/plans/ACTIVE-PLAN.md \
  || fail "block debería regenerar blockers"
python3 "$CLI" resume --next-action "implement atomic writes" >/dev/null \
  || fail "resume debería funcionar"
grep -Fq 'implement atomic writes' docs/plans/ACTIVE-PLAN.md \
  || fail "resume debería regenerar next_action"
python3 "$CLI" complete \
  --commit def456 \
  --test-command "bash tests/test-harness-state.sh" \
  --result "ALL OK" >/dev/null \
  || fail "complete debería funcionar"
grep -Fq '**Execution status:** `completed`' docs/plans/ACTIVE-PLAN.md \
  || fail "complete debería regenerar estado final"

python3 "$CLI" show --json | python3 -c '
import json, sys
d=json.load(sys.stdin)
assert d["status"] == "completed"
assert d["last_verified_commit"] == "def456"
assert d["phase"] == 2
assert d["task"] == "2.1"
assert d["last_completed_task"] == "1.1"
assert d["attempt_count"] == 1
assert d["attempt_metadata"][-1]["reason"] == "waiting for design"
assert d["checkpoint_metadata"]["commit"] == "def456"
assert len(d["history"]) >= 6
'
python3 "$CLI" validate >/dev/null || fail "estado completado debería validar"

if python3 "$CLI" resume --next-action "must fail" >/dev/null 2>&1; then
  fail "resume no debería funcionar desde completed"
fi

echo "ALL OK"
