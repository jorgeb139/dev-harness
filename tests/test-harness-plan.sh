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
      "single-agent": "50k-100k",
      "mixed": "90k-180k",
      "multi-agent": "130k-260k"
    },
    "models": {
      "architecture": "top-model",
      "implementation": "standard-model"
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
              "status": "completed",
              "evidence": "unknown-ID regression"
            }
          ],
          "test_obligations": [
            {
              "description": "Run focused plan tests",
              "status": "green",
              "command": "bash tests/test-harness-plan.sh",
              "evidence": "ALL OK"
            }
          ],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending", "evidence": "review queued"},
        "regression": {"status": "pending", "evidence": "suite queued"},
        "tests": {"status": "pending", "evidence": "coverage queued"},
        "objectives": {"status": "pending", "evidence": "phase active"}
      }
    },
    {
      "id": "2",
      "title": "Integration",
      "status": "pending",
      "objectives": [
        {
          "description": "Advance only after dependency and reviewer gates",
          "status": "pending",
          "evidence": null
        }
      ],
      "tasks": [
        {
          "id": "2.1",
          "title": "Integrate state transitions",
          "status": "pending",
          "owner_role": "owner`role",
          "reviewer_roles": ["security", "regression", "tests"],
          "dependencies": ["1.1"],
          "acceptance_criteria": [
            {
              "description": "Valid transitions preserve state atomically",
              "status": "pending",
              "evidence": null
            }
          ],
          "test_obligations": [
            {
              "description": "Run state lifecycle regression",
              "status": "pending",
              "command": "printf '`state`' && bash tests/test-harness-state.sh",
              "evidence": null
            }
          ],
          "evidence": {}
        }
      ],
      "validation": {
        "security": {"status": "pending", "evidence": "review queued"},
        "regression": {"status": "pending", "evidence": "suite queued"},
        "tests": {"status": "pending", "evidence": "coverage queued"},
        "objectives": {"status": "pending", "evidence": "phase queued"}
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
  "schema_version": 2,
  "plan_id": "demo-plan",
  "plan_file": ".harness/plan.json",
  "status": "in_progress",
  "phase": 1,
  "task": "1.1",
  "owner": "implementer",
  "branch": "codex/demo-plan",
  "last_verified_commit": "",
  "last_completed_task": null,
  "attempt_count": 0,
  "attempt_metadata": [],
  "mode_decision": null,
  "selected_mode": null,
  "token_estimates": {},
  "checkpoint_metadata": null,
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
[ -f "$PROJECT/docs/plans/ACTIVE-PLAN.state.json" ] \
  || fail "plan mode debería mantener el mirror legacy"
cmp -s "$STATE" "$PROJECT/docs/plans/ACTIVE-PLAN.state.json" \
  || fail "estado canónico y mirror legacy deberían coincidir"
grep -Fq '**User choice:** mixed' "$PROJECT/docs/plans/ACTIVE-PLAN.md" \
  || fail "plan mode debería regenerar la proyección"
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
import contextlib
import io
import json
import os
import sys
from pathlib import Path

import harness_plan
import harness_state
from harness_plan import (
    archive_plan,
    load_plan,
    record_mode_decision,
    render_markdown,
    task_index,
    validate_plan,
)
from harness_state import handoff_markdown, validate_state, validate_task_transition

root = Path(sys.argv[1])
plan_path = root / ".harness/plan.json"
state_path = root / ".harness/execution-state.json"

plan = load_plan(plan_path)
assert list(task_index(plan)) == ["1.1", "2.1"]

for mutate, expected in (
    (
        lambda value: value["phases"][0].__setitem__("objectives", ["not measurable"]),
        "objectives",
    ),
    (
        lambda value: value["phases"][0]["tasks"][0]["acceptance_criteria"][0].pop(
            "evidence"
        ),
        "evidence",
    ),
    (
        lambda value: value["mode_options"]["estimates"].pop("mixed"),
        "estimate",
    ),
    (
        lambda value: value["phases"][0]["objectives"][0].update({"evidence": None}),
        "required when complete",
    ),
    (
        lambda value: value["phases"][0]["objectives"][0].update({"evidence": False}),
        "required when complete",
    ),
    (
        lambda value: value.__setitem__("plan_id", "../unsafe"),
        "unsupported characters",
    ),
):
    invalid = copy.deepcopy(plan)
    mutate(invalid)
    try:
        validate_plan(invalid)
    except ValueError as exc:
        assert expected in str(exc)
    else:
        raise AssertionError(f"invalid canonical plan contract must fail: {expected}")

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
assert "Architecture" in rendered and "top-model" in rendered
assert "review queued" in rendered
assert "Owner role: ``owner`role``" in rendered
assert "``printf '`state`' && bash tests/test-harness-state.sh``" in rendered

sorted_round_trip = json.loads(json.dumps(plan, sort_keys=True))
sorted_state_round_trip = json.loads(json.dumps(state, sort_keys=True))
assert render_markdown(sorted_round_trip, sorted_state_round_trip) == rendered

for marker, escaped in (
    ("---", "\\---"),
    ("- item", "\\- item"),
    ("1. item", "1\\. item"),
):
    marker_plan = copy.deepcopy(plan)
    marker_plan["mode_options"]["rationale"] = marker
    marker_rendered = render_markdown(marker_plan, state)
    assert f"\n{escaped}\n" in marker_rendered
    assert f"\n{marker}\n" not in marker_rendered

for recovery_field in (
    "last_completed_task",
    "attempt_count",
    "attempt_metadata",
    "mode_decision",
    "selected_mode",
    "token_estimates",
    "checkpoint_metadata",
):
    missing_recovery = copy.deepcopy(state)
    missing_recovery.pop(recovery_field)
    try:
        validate_state(missing_recovery)
    except ValueError as exc:
        assert recovery_field in str(exc)
    else:
        raise AssertionError(f"state recovery field must be required: {recovery_field}")

wrong_current_phase = copy.deepcopy(state)
wrong_current_phase["phase"] = 2
try:
    validate_task_transition(wrong_current_phase, plan, "2", "2.1")
except ValueError as exc:
    assert "current task" in str(exc) and "phase" in str(exc)
else:
    raise AssertionError("current state phase/task mismatch must be rejected")

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
    "implementation_checkpoint": "not-green",
    "security": {"status": "green", "result": "no findings"},
    "regression": {"status": "green", "result": "ALL OK"},
    "tests": {"status": "green", "result": "ALL OK"},
}
try:
    validate_task_transition(state, plan, "2", "2.1")
except ValueError as exc:
    assert "implementation checkpoint" in str(exc)
else:
    raise AssertionError("string checkpoints must be rejected")

current["evidence"] = {
    "implementation_checkpoint": {
        "status": "green",
        "commit": "abc123",
        "test_command": "bash tests/test-harness-plan.sh",
        "result": "ALL OK",
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
        "single-agent": "50k-100k",
        "mixed": "90k-180k",
        "multi-agent": "130k-260k",
    },
    "rationale": "User selected focused independent review",
    "models": {
        "architecture": "top-model",
        "implementation": "standard-model",
    },
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
assert (root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").read_text(
    encoding="utf-8"
) == handoff_markdown(persisted_state)

try:
    archive_plan(root, persisted_plan, persisted_state, "handoff facts only")
except ValueError as exc:
    assert "incomplete" in str(exc)
else:
    raise AssertionError("incomplete plans must not archive")

complete_plan = copy.deepcopy(persisted_plan)
for phase in complete_plan["phases"]:
    phase["status"] = "completed"
    for objective in phase["objectives"]:
        objective["status"] = "completed"
        objective["evidence"] = "objective verified"
    for task in phase["tasks"]:
        task["status"] = "completed"
        task["evidence"] = copy.deepcopy(current["evidence"])
        for criterion in task["acceptance_criteria"]:
            criterion["status"] = "completed"
            criterion["evidence"] = "criterion verified"
        for obligation in task["test_obligations"]:
            obligation["status"] = "green"
            obligation["evidence"] = "ALL OK"
    for gate in phase["validation"].values():
        gate["status"] = "green"
        gate["evidence"] = "gate verified"
complete_state = copy.deepcopy(persisted_state)
complete_state.update({
    "status": "completed",
    "phase": 2,
    "task": "2.1",
    "last_verified_commit": "def456",
    "last_completed_task": "2.1",
    "checkpoint_metadata": {
        "timestamp": "2026-08-20T12:00:00+00:00",
        "commit": "def456",
        "test_command": "bash tests/test-harness-plan.sh",
        "result": "ALL OK"
    },
    "next_action": "plan complete",
})
plan_path.write_text(json.dumps(complete_plan), encoding="utf-8")
state_path.write_text(json.dumps(complete_state), encoding="utf-8")
(root / "docs/plans/ACTIVE-PLAN.state.json").write_text(
    json.dumps(complete_state), encoding="utf-8"
)
(root / "docs/plans/ACTIVE-PLAN.md").write_text(
    render_markdown(complete_plan, complete_state), encoding="utf-8"
)
(root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").write_text(
    handoff_markdown(complete_state), encoding="utf-8"
)

history_path = archive_plan(
    root,
    complete_plan,
    complete_state,
    (root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").read_text(encoding="utf-8"),
)
assert history_path == root.resolve() / "docs/plans/history/demo-plan.md"
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


def active_snapshots(probe_root, probe_plan, probe_state, handoff=None):
    (probe_root / ".harness").mkdir(parents=True, exist_ok=True)
    (probe_root / "docs/plans").mkdir(parents=True, exist_ok=True)
    plan_text = json.dumps(probe_plan, indent=2, sort_keys=True) + "\n"
    state_text = json.dumps(probe_state, indent=2, sort_keys=True) + "\n"
    (probe_root / ".harness/plan.json").write_text(plan_text, encoding="utf-8")
    (probe_root / ".harness/execution-state.json").write_text(state_text, encoding="utf-8")
    (probe_root / "docs/plans/ACTIVE-PLAN.state.json").write_text(
        state_text, encoding="utf-8"
    )
    (probe_root / "docs/plans/ACTIVE-PLAN.md").write_text(
        render_markdown(probe_plan, probe_state), encoding="utf-8"
    )
    handoff_text = handoff_markdown(probe_state) if handoff is None else handoff
    (probe_root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").write_text(
        handoff_text, encoding="utf-8"
    )


def completed_probe(probe_id):
    probe_plan = copy.deepcopy(complete_plan)
    probe_state = copy.deepcopy(complete_state)
    probe_plan["plan_id"] = probe_id
    probe_plan["title"] = probe_id
    probe_state["plan_id"] = probe_id
    return probe_plan, probe_state


for label, mutate in (
    (
        "pending-objective",
        lambda value: value["phases"][0]["objectives"][0].update(
            {"status": "pending", "evidence": None}
        ),
    ),
    (
        "pending-criterion",
        lambda value: value["phases"][0]["tasks"][0]["acceptance_criteria"][0].update(
            {"status": "pending", "evidence": None}
        ),
    ),
    (
        "pending-obligation",
        lambda value: value["phases"][0]["tasks"][0]["test_obligations"][0].update(
            {"status": "pending", "evidence": None}
        ),
    ),
    (
        "null-only-objective",
        lambda value: value["phases"][0]["objectives"][0].update(
            {"evidence": {"placeholder": None}}
        ),
    ),
    (
        "null-only-criterion",
        lambda value: value["phases"][0]["tasks"][0]["acceptance_criteria"][0].update(
            {"evidence": [None, {"placeholder": False}]}
        ),
    ),
    (
        "null-only-obligation",
        lambda value: value["phases"][0]["tasks"][0]["test_obligations"][0].update(
            {"evidence": {"nested": [None, False, ""]}}
        ),
    ),
):
    probe_plan, probe_state = completed_probe(label)
    mutate(probe_plan)
    probe_root = root.parent / label
    if label.startswith("null-only-"):
        (probe_root / ".harness").mkdir(parents=True, exist_ok=True)
        (probe_root / "docs/plans").mkdir(parents=True, exist_ok=True)
        plan_text = json.dumps(probe_plan, indent=2, sort_keys=True) + "\n"
        state_text = json.dumps(probe_state, indent=2, sort_keys=True) + "\n"
        (probe_root / ".harness/plan.json").write_text(plan_text, encoding="utf-8")
        (probe_root / ".harness/execution-state.json").write_text(
            state_text, encoding="utf-8"
        )
        (probe_root / "docs/plans/ACTIVE-PLAN.state.json").write_text(
            state_text, encoding="utf-8"
        )
        (probe_root / "docs/plans/ACTIVE-PLAN.md").write_text(
            "invalid evidence must not archive\n", encoding="utf-8"
        )
        (probe_root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").write_text(
            handoff_markdown(probe_state), encoding="utf-8"
        )
    else:
        active_snapshots(probe_root, probe_plan, probe_state)
    try:
        archive_plan(probe_root, probe_plan, probe_state, handoff_markdown(probe_state))
    except ValueError as exc:
        assert "incomplete" in str(exc) or "evidence" in str(exc)
    else:
        raise AssertionError(f"archive must reject {label}")

sensitive_cases = {
    "secret-api-key": {"api_key": "abc123"},
    "secret-bearer": {"note": "Bearer abc123"},
    "secret-private-key": {"note": "-----BEGIN PRIVATE KEY-----"},
    "secret-password": {"password": "hunter2"},
    "secret-credential-url": {"url": "https://user:pass@example.test/repo"},
}
for probe_id, sensitive_impact in sensitive_cases.items():
    probe_plan, probe_state = completed_probe(probe_id)
    probe_plan["impact_analysis"] = sensitive_impact
    probe_root = root.parent / probe_id
    active_snapshots(probe_root, probe_plan, probe_state)
    try:
        archive_plan(probe_root, probe_plan, probe_state, handoff_markdown(probe_state))
    except ValueError as exc:
        assert "sensitive" in str(exc)
    else:
        raise AssertionError(f"archive must reject sensitive pattern {probe_id}")

handoff_plan, handoff_state = completed_probe("secret-handoff")
handoff_root = root.parent / "secret-handoff"
active_snapshots(handoff_root, handoff_plan, handoff_state, "password=hidden")
try:
    archive_plan(handoff_root, handoff_plan, handoff_state, "password=hidden")
except ValueError as exc:
    assert "sensitive" in str(exc)
else:
    raise AssertionError("archive must scan raw handoff text")

safe_plan, safe_state = completed_probe("safe-boundaries")
safe_plan["impact_analysis"] = {
    "password_policy": "documented",
    "api_key_hint": "not stored",
    "authorization": "Token authentication is documented without a credential",
    "url": "https://example.test/repo",
}
safe_root = root.parent / "safe-boundaries"
active_snapshots(safe_root, safe_plan, safe_state)
safe_archive = archive_plan(safe_root, safe_plan, safe_state, handoff_markdown(safe_state))
assert safe_archive.is_file()

blocked_plan, blocked_state = completed_probe("blocked-state")
blocked_state["status"] = "blocked"
blocked_state["blockers"] = ["unresolved blocker"]
blocked_root = root.parent / "blocked-state"
active_snapshots(blocked_root, blocked_plan, blocked_state)
try:
    archive_plan(blocked_root, blocked_plan, blocked_state, "handoff facts only")
except ValueError as exc:
    assert "incomplete" in str(exc) or "blocked" in str(exc)
else:
    raise AssertionError("blocked state must not archive")

cross_plan, cross_state = completed_probe("cross-plan-caller")
active_cross_plan, active_cross_state = completed_probe("cross-plan-active")
cross_root = root.parent / "cross-plan-active"
active_snapshots(cross_root, active_cross_plan, active_cross_state)
try:
    archive_plan(cross_root, cross_plan, cross_state, "handoff facts only")
except ValueError as exc:
    assert "stale" in str(exc) or "different plan" in str(exc)
else:
    raise AssertionError("cross-plan active snapshots must not archive")
assert (cross_root / ".harness/plan.json").is_file()

stale_plan, stale_state = completed_probe("stale-same-id")
newer_plan = copy.deepcopy(stale_plan)
newer_plan["title"] = "NEWER ACTIVE PLAN"
newer_plan["history"].append({
    "event": "newer",
    "timestamp": "2026-08-20T13:00:00+00:00",
    "detail": "new active revision",
})
stale_root = root.parent / "stale-same-id"
active_snapshots(stale_root, newer_plan, stale_state)
try:
    archive_plan(stale_root, stale_plan, stale_state, "handoff facts only")
except ValueError as exc:
    assert "stale" in str(exc)
else:
    raise AssertionError("stale same-plan archive callers must be rejected")
assert load_plan(stale_root / ".harness/plan.json")["title"] == "NEWER ACTIVE PLAN"
assert (stale_root / ".harness/execution-state.json").is_file()

stale_state_plan, stale_state = completed_probe("stale-same-id-state")
newer_state = copy.deepcopy(stale_state)
newer_state["updated_at"] = "2026-08-20T14:00:00+00:00"
newer_state["history"].append({
    "event": "newer",
    "timestamp": "2026-08-20T14:00:00+00:00",
    "detail": "new active state revision",
})
stale_state_root = root.parent / "stale-same-id-state"
active_snapshots(stale_state_root, stale_state_plan, newer_state)
try:
    archive_plan(
        stale_state_root, stale_state_plan, stale_state, "handoff facts only"
    )
except ValueError as exc:
    assert "stale" in str(exc) and "state" in str(exc)
else:
    raise AssertionError("stale same-plan state callers must be rejected")
assert json.loads(
    (stale_state_root / ".harness/execution-state.json").read_text(encoding="utf-8")
)["updated_at"] == "2026-08-20T14:00:00+00:00"

pointer_plan, pointer_state = completed_probe("pointer-a")
other_plan, other_state = completed_probe("pointer-b")
pointer_root = root.parent / "cross-plan-state-pointer"
active_snapshots(pointer_root, pointer_plan, pointer_state)
(pointer_root / "docs/plans/ACTIVE-PLAN.state.json").write_text(
    json.dumps(other_state), encoding="utf-8"
)
try:
    archive_plan(pointer_root, pointer_plan, pointer_state, "handoff facts only")
except ValueError:
    pass
else:
    raise AssertionError("divergent canonical/legacy state must fail closed")
assert (pointer_root / ".harness/plan.json").is_file()
assert (pointer_root / "docs/plans/ACTIVE-PLAN.state.json").is_file()

markdown_root = root.parent / "cross-plan-markdown-pointer"
active_snapshots(markdown_root, pointer_plan, pointer_state)
(markdown_root / "docs/plans/ACTIVE-PLAN.md").write_text(
    render_markdown(other_plan, other_state), encoding="utf-8"
)
try:
    archive_plan(markdown_root, pointer_plan, pointer_state, handoff_markdown(pointer_state))
except ValueError as exc:
    assert "pointer" in str(exc) or "ownership" in str(exc)
else:
    raise AssertionError("unrelated Markdown pointer must survive archive")
assert "pointer-b" in (markdown_root / "docs/plans/ACTIVE-PLAN.md").read_text(
    encoding="utf-8"
)

handoff_pointer_root = root.parent / "cross-plan-handoff-pointer"
active_snapshots(handoff_pointer_root, pointer_plan, pointer_state, "pointer-b handoff")
try:
    archive_plan(handoff_pointer_root, pointer_plan, pointer_state, "pointer-a handoff")
except ValueError as exc:
    assert "handoff" in str(exc) or "pointer" in str(exc)
else:
    raise AssertionError("unrelated handoff pointer must survive archive")
assert (handoff_pointer_root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").read_text(
    encoding="utf-8"
) == "pointer-b handoff"

mode_plan = copy.deepcopy(plan)
mode_plan["mode_options"]["choice"] = None
mode_state = copy.deepcopy(state)
mode_state["selected_mode"] = None
mode_state["token_estimates"] = {}
mode_state["mode_decision"] = None
mode_root = root.parent / "mode-recovery"
active_snapshots(mode_root, mode_plan, mode_state)
mode_plan_path = mode_root / ".harness/plan.json"
mode_state_path = (mode_root / ".harness/execution-state.json").resolve()
mode_plan_path = mode_plan_path.resolve()
original_atomic_json = harness_state.atomic_write_json
mode_failed = False


def fail_mode_state_once(path, value):
    global mode_failed
    if Path(path) == mode_state_path and not mode_failed:
        mode_failed = True
        raise OSError("injected mode state publish failure")
    return original_atomic_json(path, value)


harness_state.atomic_write_json = fail_mode_state_once
try:
    record_mode_decision(mode_plan_path, mode_state_path, decision)
except OSError as exc:
    assert "injected mode" in str(exc)
else:
    raise AssertionError("mode failure injection must interrupt publication")
finally:
    harness_state.atomic_write_json = original_atomic_json
assert list((mode_root / ".harness/transactions").glob("*/manifest.json"))
record_mode_decision(mode_plan_path, mode_state_path, decision)
assert load_plan(mode_plan_path)["mode_options"]["choice"] == "mixed"
recovered_mode_state = json.loads(mode_state_path.read_text(encoding="utf-8"))
assert recovered_mode_state["selected_mode"] == "mixed"
assert json.loads(
    (mode_root / "docs/plans/ACTIVE-PLAN.state.json").read_text(encoding="utf-8")
) == recovered_mode_state
assert "**User choice:** mixed" in (
    mode_root / "docs/plans/ACTIVE-PLAN.md"
).read_text(encoding="utf-8")
assert (mode_root / "docs/plans/ACTIVE-PLAN.HANDOFF.md").read_text(
    encoding="utf-8"
) == handoff_markdown(recovered_mode_state)

partial_plan, partial_state = completed_probe("partial-archive")
partial_root = root.parent / "partial-archive"
active_snapshots(partial_root, partial_plan, partial_state)
partial_state_archive = (
    partial_root / "docs/plans/history/partial-archive.state.json"
).resolve()
archive_failed = False


def fail_archive_state_once(path, value):
    global archive_failed
    if Path(path) == partial_state_archive and not archive_failed:
        archive_failed = True
        raise OSError("injected archive state publish failure")
    return original_atomic_json(path, value)


harness_state.atomic_write_json = fail_archive_state_once
try:
    archive_plan(partial_root, partial_plan, partial_state, handoff_markdown(partial_state))
except OSError as exc:
    assert "injected archive" in str(exc)
else:
    raise AssertionError("archive failure injection must interrupt publication")
finally:
    harness_state.atomic_write_json = original_atomic_json
assert list((partial_root / ".harness/transactions").glob("*/manifest.json"))
assert (partial_root / ".harness/plan.json").is_file()
recovered_archive = archive_plan(
    partial_root, partial_plan, partial_state, handoff_markdown(partial_state)
)
assert recovered_archive.is_file()
assert partial_state_archive.is_file()
assert not (partial_root / ".harness/plan.json").exists()

cleanup_plan, cleanup_state = completed_probe("post-delete-retry")
cleanup_root = root.parent / "post-delete-retry"
active_snapshots(cleanup_root, cleanup_plan, cleanup_state)
cleanup_archive = cleanup_root / "docs/plans/history/post-delete-retry.md"
original_clear_transaction = harness_state._clear_transaction_directory
cleanup_failed = False


def fail_cleanup_after_delete_once(directory):
    global cleanup_failed
    if (
        Path(directory).name == "archive-post-delete-retry"
        and not (cleanup_root / ".harness/plan.json").exists()
        and not cleanup_failed
    ):
        cleanup_failed = True
        raise OSError("injected post-delete cleanup failure")
    return original_clear_transaction(directory)


previous_cwd = Path.cwd()
os.chdir(cleanup_root)
harness_state._clear_transaction_directory = fail_cleanup_after_delete_once
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        first_rc = harness_plan.main(["plan", "archive"])
finally:
    harness_state._clear_transaction_directory = original_clear_transaction
assert first_rc == 1
assert cleanup_archive.is_file()
assert not (cleanup_root / ".harness/plan.json").exists()
assert (
    cleanup_root / ".harness/transactions/archive-post-delete-retry/manifest.json"
).is_file()
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    retry_rc = harness_plan.main(["plan", "archive"])
os.chdir(previous_cwd)
assert retry_rc == 0
assert cleanup_archive.is_file()
assert not (
    cleanup_root / ".harness/transactions/archive-post-delete-retry/manifest.json"
).exists()
PY
then
  fail "plan schema, projection, gates, mode, and archive contract"
fi

echo "ALL OK"
