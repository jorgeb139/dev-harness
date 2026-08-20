#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/scripts/harness-state.py"
fail() { echo "FAIL: $1"; exit 1; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/project/docs/plans"
printf '# Plan: demo\n' > "$TMP/project/docs/plans/ACTIVE-PLAN.md"
cd "$TMP/project"

python3 "$CLI" init \
  --plan-id demo \
  --plan-file docs/plans/ACTIVE-PLAN.md \
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
python3 "$CLI" advance \
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
