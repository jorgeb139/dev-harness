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
import copy
import json
from pathlib import Path
import sys

from harness_plan import load_plan
from harness_state import (
    load_state,
    resolve_execution_state,
    validate_state,
    validate_task_transition,
)

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
assert canonical_value["mode_decision"] is None
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

v1_value = copy.deepcopy(canonical_value)
v1_value["schema_version"] = 1
for field in (
    "last_completed_task",
    "attempt_count",
    "attempt_metadata",
    "mode_decision",
    "selected_mode",
    "token_estimates",
    "checkpoint_metadata",
):
    v1_value.pop(field)
v1_path = root / ".harness/schema-v1-state.json"
v1_path.write_text(json.dumps(v1_value), encoding="utf-8")
migrated = load_state(v1_path)
assert migrated["schema_version"] == 2
assert migrated["last_completed_task"] is None
assert migrated["attempt_count"] == 0
assert migrated["attempt_metadata"] == []
assert migrated["mode_decision"] is None
assert migrated["selected_mode"] is None
assert migrated["token_estimates"] == {}
assert migrated["checkpoint_metadata"] is None

early_v2_value = copy.deepcopy(canonical_value)
early_v2_value.pop("mode_decision")
early_v2_path = root / ".harness/early-schema-v2-state.json"
early_v2_path.write_text(json.dumps(early_v2_value), encoding="utf-8")
early_v2_migrated = load_state(early_v2_path)
assert early_v2_migrated["schema_version"] == 2
assert early_v2_migrated["mode_decision"] is None

for bad_state in (
    {
        **copy.deepcopy(canonical_value),
        "selected_mode": "mixed",
        "token_estimates": {"other": "1k"},
        "mode_decision": {
            "recommendation": "mixed",
            "choice": "mixed",
            "estimates": {"other": "1k"},
        },
    },
    {
        **copy.deepcopy(canonical_value),
        "selected_mode": "mixed",
        "token_estimates": {"mixed": "1k"},
        "mode_decision": {
            "recommendation": "mixed",
            "choice": "single-agent",
            "estimates": {"mixed": "1k"},
        },
    },
):
    try:
        validate_state(bad_state)
    except ValueError as exc:
        assert "mode" in str(exc) or "estimate" in str(exc)
    else:
        raise AssertionError("state mode decision and estimates must remain coherent")

singleton_mode_state = copy.deepcopy(canonical_value)
singleton_mode_state.update({
    "selected_mode": "mixed",
    "token_estimates": {"mixed": "1k"},
    "mode_decision": {
        "recommendation": "mixed",
        "choice": "mixed",
        "estimates": {"mixed": "1k"},
    },
})
validate_state(singleton_mode_state)
try:
    validate_task_transition(
        singleton_mode_state,
        load_plan(root / ".harness/plan.json"),
        "2",
        "2.1",
    )
except ValueError as exc:
    assert "mode" in str(exc) and ("declared" in str(exc) or "plan" in str(exc))
else:
    raise AssertionError("state estimates must cover every mode declared by the plan")
PY

PYTHONPATH="$ROOT/scripts" python3 - "$TMP" "$CLI" <<'PY' \
  || { echo "FAIL: contención de manifests de recuperación"; exit 1; }
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from harness_state import resume_transaction

base = Path(sys.argv[1]).resolve()
cli = Path(sys.argv[2]).resolve()


def sha(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def write_manifest(probe, transaction_id, destination, staged, deletes=()):
    directory = probe / ".harness/transactions" / transaction_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "transaction_id": transaction_id,
        "metadata": {},
        "writes": [{
            "destination": destination,
            "staged": staged,
            "kind": "text",
            "before": None,
            "desired": sha("payload"),
        }],
        "deletes": [
            {"destination": path, "before": fingerprint}
            for path, fingerprint in deletes
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return directory


def expect_rejected(probe, transaction_id, protected, untouched):
    try:
        resume_transaction(probe, transaction_id)
    except ValueError as exc:
        assert "path" in str(exc) or "escape" in str(exc) or "manifest" in str(exc)
    else:
        raise AssertionError(f"unsafe recovery manifest must fail: {transaction_id}")
    for path in protected:
        assert path.exists(), f"recovery deleted protected path: {path}"
    for path in untouched:
        assert not path.exists(), f"recovery wrote before complete validation: {path}"


probe = base / "manifest-destination-traversal"
outside = base / "outside-destination.txt"
directory = write_manifest(probe, "evil-write", "../outside-destination.txt", "payload")
(directory / "payload").write_text("payload", encoding="utf-8")
expect_rejected(probe, "evil-write", [], [outside])

probe = base / "manifest-absolute-destination"
outside = base / "outside-absolute.txt"
directory = write_manifest(probe, "evil-absolute", str(outside), "payload")
(directory / "payload").write_text("payload", encoding="utf-8")
expect_rejected(probe, "evil-absolute", [], [outside])

probe = base / "manifest-staged-traversal"
outside_payload = base / "outside-staged.payload"
outside_payload.write_text("payload", encoding="utf-8")
directory = write_manifest(
    probe,
    "evil-staged",
    "inside.txt",
    os.path.relpath(outside_payload, probe / ".harness/transactions/evil-staged"),
)
expect_rejected(probe, "evil-staged", [outside_payload], [probe / "inside.txt"])

probe = base / "manifest-absolute-staged"
outside_payload = base / "outside-absolute.payload"
outside_payload.write_text("payload", encoding="utf-8")
write_manifest(probe, "evil-absolute-staged", "inside.txt", str(outside_payload))
expect_rejected(
    probe, "evil-absolute-staged", [outside_payload], [probe / "inside.txt"]
)

probe = base / "manifest-destination-symlink"
probe.mkdir(parents=True)
(probe / "escape").symlink_to(base, target_is_directory=True)
outside = base / "outside-symlink.txt"
directory = write_manifest(probe, "evil-destination-link", "escape/outside-symlink.txt", "payload")
(directory / "payload").write_text("payload", encoding="utf-8")
expect_rejected(probe, "evil-destination-link", [], [outside])

probe = base / "manifest-staged-symlink"
outside_payload = base / "outside-link.payload"
outside_payload.write_text("payload", encoding="utf-8")
directory = write_manifest(probe, "evil-staged-link", "inside.txt", "payload-link")
(directory / "payload-link").symlink_to(outside_payload)
expect_rejected(probe, "evil-staged-link", [outside_payload], [probe / "inside.txt"])

probe = base / "manifest-directory-symlink"
(probe / ".harness/transactions").mkdir(parents=True)
outside_directory = base / "outside-transaction-directory"
outside_directory.mkdir()
outside_sentinel = outside_directory / "must-survive.txt"
outside_sentinel.write_text("protected", encoding="utf-8")
(probe / ".harness/transactions/evil-directory-link").symlink_to(
    outside_directory, target_is_directory=True
)
try:
    resume_transaction(probe, "evil-directory-link")
except ValueError as exc:
    assert "transaction" in str(exc) and ("path" in str(exc) or "root" in str(exc))
else:
    raise AssertionError("symlinked transaction directories must fail closed")
assert outside_sentinel.exists()

for name, delete_destination, use_symlink in (
    ("evil-delete", "../outside-delete.txt", False),
    ("evil-delete-link", "escape/outside-delete-link.txt", True),
):
    probe = base / f"manifest-{name}"
    probe.mkdir(parents=True)
    outside = base / ("outside-delete-link.txt" if use_symlink else "outside-delete.txt")
    outside.write_text("protected", encoding="utf-8")
    if use_symlink:
        (probe / "escape").symlink_to(base, target_is_directory=True)
    fingerprint = hashlib.sha256(outside.read_bytes()).hexdigest()
    directory = write_manifest(
        probe, name, "inside.txt", "payload", [(delete_destination, fingerprint)]
    )
    (directory / "payload").write_text("payload", encoding="utf-8")
    expect_rejected(probe, name, [outside], [probe / "inside.txt"])

cli_probe = base / "manifest-cli-show"
(cli_probe / ".harness").mkdir(parents=True)
(cli_probe / "docs/plans").mkdir(parents=True)
source_state = json.loads(
    (base / "project/.harness/execution-state.json").read_text(encoding="utf-8")
)
state_text = json.dumps(source_state)
(cli_probe / ".harness/execution-state.json").write_text(state_text, encoding="utf-8")
(cli_probe / "docs/plans/ACTIVE-PLAN.state.json").write_text(state_text, encoding="utf-8")
cli_outside = base / "outside-cli-show.txt"
directory = write_manifest(
    cli_probe, "execution-state", "../outside-cli-show.txt", "payload"
)
(directory / "payload").write_text("payload", encoding="utf-8")
result = subprocess.run(
    [sys.executable, str(cli), "show"],
    cwd=cli_probe,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    check=False,
)
assert result.returncode == 1
assert not cli_outside.exists()
PY

PYTHONPATH="$ROOT/scripts" python3 - "$TMP/lock-project" <<'PY' \
  || { echo "FAIL: identidad estable del lock transaccional"; exit 1; }
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path(sys.argv[1]).resolve()
(root / ".harness/transactions/lock-probe").mkdir(parents=True)
ready = root / "first-ready"
acquired = root / "second-acquired"
holder_code = """
import sys, time
from pathlib import Path
from harness_state import locked_paths, resume_transaction, transaction_lock_path
root = Path(sys.argv[1]).resolve()
with locked_paths([transaction_lock_path(root, 'lock-probe')]):
    resume_transaction(root, 'lock-probe')
    (root / 'first-ready').write_text('ready', encoding='utf-8')
    time.sleep(1.0)
"""
waiter_code = """
import sys
from pathlib import Path
from harness_state import locked_paths, transaction_lock_path
root = Path(sys.argv[1]).resolve()
with locked_paths([transaction_lock_path(root, 'lock-probe')]):
    (root / 'second-acquired').write_text('acquired', encoding='utf-8')
"""
environment = dict(os.environ)
holder = subprocess.Popen(
    [sys.executable, "-c", holder_code, str(root)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=environment,
)
deadline = time.monotonic() + 3
while not ready.exists() and holder.poll() is None and time.monotonic() < deadline:
    time.sleep(0.02)
if not ready.exists():
    stdout, stderr = holder.communicate(timeout=2)
    raise AssertionError(f"lock holder did not initialize: {stdout} {stderr}")
waiter = subprocess.Popen(
    [sys.executable, "-c", waiter_code, str(root)],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    env=environment,
)
time.sleep(0.25)
assert not acquired.exists(), "second process acquired transaction lock before release"
holder_stdout, holder_stderr = holder.communicate(timeout=3)
waiter_stdout, waiter_stderr = waiter.communicate(timeout=3)
assert holder.returncode == 0, (holder_stdout, holder_stderr)
assert waiter.returncode == 0, (waiter_stdout, waiter_stderr)
assert acquired.exists()
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
plan["phases"][0]["tasks"][0]["evidence"]["security"] = {"status": "green"}
path.write_text(json.dumps(plan), encoding="utf-8")
PY

if python3 "$CLI" advance \
  --plan-json .harness/plan.json \
  --phase 2 \
  --task 2.1 \
  --next-action "must fail" >/dev/null 2>&1; then
  fail "advance debería rechazar revisiones verdes sin resultado"
fi

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
assert d["last_completed_task"] == "2.1"
assert d["attempt_count"] == 1
assert d["attempt_metadata"][-1]["reason"] == "waiting for design"
assert d["checkpoint_metadata"]["commit"] == "def456"
assert len(d["history"]) >= 6
'
python3 "$CLI" validate >/dev/null || fail "estado completado debería validar"

PYTHONPATH="$ROOT/scripts" python3 - <<'PY' \
  || { echo "FAIL: escape de marcadores Markdown en handoff"; exit 1; }
import json
from pathlib import Path

from harness_state import handoff_markdown

state = json.loads(Path(".harness/execution-state.json").read_text(encoding="utf-8"))
for marker, escaped in (
    ("---", "\\---"),
    ("- item", "\\- item"),
    ("1. item", "1\\. item"),
):
    state["next_action"] = marker
    rendered = handoff_markdown(state)
    assert f"\n{escaped}\n" in rendered
    assert f"\n{marker}\n" not in rendered
PY

if python3 "$CLI" resume --next-action "must fail" >/dev/null 2>&1; then
  fail "resume no debería funcionar desde completed"
fi

echo "ALL OK"
