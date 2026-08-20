#!/bin/bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/scripts/harness-plan.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $1"; exit 1; }

PROJECT="$TMP/project"
PLAN="$PROJECT/.harness/plan.json"
STATE="$PROJECT/.harness/execution-state.json"
mkdir -p "$PROJECT/.harness" "$PROJECT/docs/plans"

cat > "$PLAN" <<'JSON'
{
  "schema_version": 1,
  "plan_id": "demo-plan",
  "title": "Demo *structured* plan",
  "original_scope": ["Build a canonical plan"],
  "approved_scope": ["Build the plan, projection, and gates"],
  "assumptions": ["Python 3 is available"],
  "impact_analysis": {
    "backward": ["state CLI"],
    "forward": ["session and commit hooks"],
    "risks": ["Unknown [task] identifiers"]
  },
  "questions": [
    {
      "text": "Where is history written?",
      "status": "resolved",
      "answer": "docs/plans/history"
    }
  ],
  "mode_options": {
    "recommendation": "multi-agent",
    "choice": null,
    "options": ["single-agent", "mixed", "multi-agent"],
    "estimates": {
      "single_agent": "50k-100k",
      "mixed": "90k-180k",
      "multi_agent": "130k-260k"
    }
  },
  "phases": [
    {
      "id": "1",
      "title": "Canonical model",
      "status": "in_progress",
      "objectives": [
        {
          "description": "Validate stable task IDs",
          "status": "completed",
          "evidence": "focused plan test"
        }
      ],
      "tasks": [
        {
          "id": "1.1",
          "title": "Create schema and projection",
          "status": "in_progress",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": [],
          "acceptance_criteria": [
            {
              "description": "Reject unknown task IDs",
              "status": "completed"
            }
          ],
          "test_obligations": [
            {
              "description": "Run focused plan tests",
              "status": "green",
              "command": "bash tests/test-harness-plan.sh"
            }
          ],
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
      "title": "Integration",
      "status": "pending",
      "objectives": ["Advance only after dependency and reviewer gates"],
      "tasks": [
        {
          "id": "2.1",
          "title": "Integrate state transitions",
          "status": "pending",
          "owner_role": "implementer",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": ["1.1"],
          "acceptance_criteria": ["Valid transitions preserve state atomically"],
          "test_obligations": ["Run state lifecycle regression"],
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
  "history": [
    {
      "event": "approved",
      "timestamp": "2026-08-20T12:00:00+00:00",
      "detail": "scope approved"
    }
  ]
}
JSON

cat > "$STATE" <<'JSON'
{
  "schema_version": 1,
  "plan_id": "demo-plan",
  "plan_file": ".harness/plan.json",
  "status": "in_progress",
  "phase": 1,
  "task": "1.1",
  "owner": "implementer",
  "branch": "codex/demo-plan",
  "last_verified_commit": "",
  "next_action": "finish task 1.1",
  "evidence": [],
  "blockers": [],
  "updated_at": "2026-08-20T12:00:00+00:00",
  "history": [
    {
      "event": "started",
      "timestamp": "2026-08-20T12:00:00+00:00",
      "detail": "task=1.1"
    }
  ]
}
JSON

python3 "$CLI" plan validate --plan-json "$PLAN" >/dev/null \
  || fail "plan validate debería aceptar un plan válido"
python3 "$CLI" plan render \
  --plan-json "$PLAN" \
  --state-json "$STATE" \
  --output "$PROJECT/docs/plans/ACTIVE-PLAN.md" >/dev/null \
  || fail "plan render debería generar la proyección"
grep -Fq '**Current task:** ► Phase 1, task 1.1' \
  "$PROJECT/docs/plans/ACTIVE-PLAN.md" \
  || fail "plan render debería conservar el marcador de tarea actual"
python3 "$CLI" plan mode \
  --plan-json "$PLAN" \
  --state-json "$STATE" \
  --recommendation multi-agent \
  --choice mixed \
  --single-estimate 50k-100k \
  --mixed-estimate 90k-180k \
  --multi-estimate 130k-260k \
  --rationale "User selected focused independent review" >/dev/null \
  || fail "plan mode debería persistir la decisión"
printf 'handoff facts only\n' > "$PROJECT/docs/plans/ACTIVE-PLAN.HANDOFF.md"
if python3 "$CLI" plan archive \
  --root "$PROJECT" \
  --plan-json "$PLAN" \
  --state-json "$STATE" \
  --handoff-file "$PROJECT/docs/plans/ACTIVE-PLAN.HANDOFF.md" >/dev/null 2>&1; then
  fail "plan archive debería rechazar un plan incompleto"
fi

if ! PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" <<'PY'
import copy
import json
import sys
from pathlib import Path

from harness_plan import (
    archive_plan,
    load_plan,
    record_mode_decision,
    render_markdown,
    task_index,
    validate_plan,
)
from harness_state import validate_task_transition

root = Path(sys.argv[1])
plan_path = root / ".harness/plan.json"
state_path = root / ".harness/execution-state.json"

plan = load_plan(plan_path)
assert list(task_index(plan)) == ["1.1", "2.1"]

invalid_plan = copy.deepcopy(plan)
invalid_plan["phases"][1]["tasks"][0]["dependencies"] = ["missing-task"]
try:
    validate_plan(invalid_plan)
except ValueError as exc:
    assert "unknown dependency task ID" in str(exc)
else:
    raise AssertionError("unknown dependency task IDs must be rejected")

state = json.loads(state_path.read_text(encoding="utf-8"))
rendered = render_markdown(plan, state)
assert "GENERATED FILE" in rendered
assert "**Current task:** ► Phase 1, task 1.1" in rendered
assert "- [ ] `1.1` Create schema and projection" in rendered
assert "- [x] Validate stable task IDs" in rendered
assert "Demo \\*structured\\* plan" in rendered
assert "Unknown \\[task\\] identifiers" in rendered

try:
    validate_task_transition(state, plan, "2", "missing-task")
except ValueError as exc:
    assert "unknown target task ID" in str(exc)
else:
    raise AssertionError("unknown task IDs must be rejected")

try:
    validate_task_transition(state, plan, "2", "2.1")
except ValueError as exc:
    assert "incomplete dependencies" in str(exc)
else:
    raise AssertionError("incomplete dependencies must be rejected")

current = task_index(plan)["1.1"]
current["status"] = "completed"
current["evidence"] = {
    "implementation_checkpoint": {
        "status": "green",
        "commit": "abc123",
    },
    "regression": {"status": "green", "result": "ALL OK"},
    "tests": {"status": "green", "result": "ALL OK"},
}
try:
    validate_task_transition(state, plan, "2", "2.1")
except ValueError as exc:
    assert "security review evidence" in str(exc)
else:
    raise AssertionError("missing review evidence must be rejected")

current["evidence"]["security"] = {"status": "green", "result": "no findings"}
validate_task_transition(state, plan, "2", "2.1")

decision = {
    "recommendation": "multi-agent",
    "choice": "mixed",
    "estimates": {
        "single_agent": "50k-100k",
        "mixed": "90k-180k",
        "multi_agent": "130k-260k",
    },
    "rationale": "User selected focused independent review",
}
record_mode_decision(plan_path, state_path, decision)
persisted_plan = load_plan(plan_path)
persisted_state = json.loads(state_path.read_text(encoding="utf-8"))
assert persisted_plan["mode_options"]["recommendation"] == "multi-agent"
assert persisted_plan["mode_options"]["choice"] == "mixed"
assert persisted_plan["mode_options"]["estimates"] == decision["estimates"]
assert persisted_state["selected_mode"] == "mixed"
assert persisted_state["token_estimates"] == decision["estimates"]
assert persisted_state["mode_decision"]["recommendation"] == "multi-agent"

try:
    archive_plan(root, persisted_plan, persisted_state, "handoff facts only")
except ValueError as exc:
    assert "incomplete" in str(exc)
else:
    raise AssertionError("incomplete plans must not archive")

complete_plan = copy.deepcopy(persisted_plan)
for phase in complete_plan["phases"]:
    phase["status"] = "completed"
    for task in phase["tasks"]:
        task["status"] = "completed"
        task["evidence"] = copy.deepcopy(current["evidence"])
    for gate in phase["validation"].values():
        gate["status"] = "green"
complete_state = copy.deepcopy(persisted_state)
complete_state.update({
    "status": "completed",
    "phase": 2,
    "task": "2.1",
    "last_verified_commit": "def456",
    "next_action": "plan complete",
})
plan_path.write_text(json.dumps(complete_plan), encoding="utf-8")
state_path.write_text(json.dumps(complete_state), encoding="utf-8")
(root / "docs/plans/ACTIVE-PLAN.md").write_text("active pointer", encoding="utf-8")

history_path = archive_plan(root, complete_plan, complete_state, "handoff facts only")
assert history_path == root / "docs/plans/history/demo-plan.md"
assert history_path.is_file()
assert (history_path.parent / "demo-plan.plan.json").is_file()
assert (history_path.parent / "demo-plan.state.json").is_file()
assert (history_path.parent / "demo-plan.handoff.json").is_file()
assert (history_path.parent / "demo-plan.evidence.json").is_file()
assert not plan_path.exists()
assert not state_path.exists()
assert not (root / "docs/plans/ACTIVE-PLAN.md").exists()
assert len(list(history_path.parent.glob("*.md"))) == 1
archived_state = json.loads(
    (history_path.parent / "demo-plan.state.json").read_text(encoding="utf-8")
)
assert archived_state["last_verified_commit"] == "def456"
PY
then
  fail "plan schema, projection, gates, mode, and archive contract"
fi

echo "ALL OK"
