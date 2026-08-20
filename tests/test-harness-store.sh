#!/bin/bash
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PROJECT="$TMP/project"
mkdir -p "$PROJECT"

PYTHONPATH="$ROOT/scripts" python3 - "$PROJECT" <<'PY'
import json
import sys
from pathlib import Path

from harness_store import atomic_write_json, fingerprint_files, load_json

root = Path(sys.argv[1])
payload = root / "state.json"

atomic_write_json(payload, {"first": True, "nested": {"value": 1}})
assert json.loads(payload.read_text(encoding="utf-8")) == {
    "first": True,
    "nested": {"value": 1},
}

atomic_write_json(payload, {"second": True})
assert load_json(payload) == {"second": True}

payload.write_text("{malformed", encoding="utf-8")
try:
    load_json(payload)
except ValueError:
    pass
else:
    raise AssertionError("malformed JSON should be rejected")

listed = root / "listed.txt"
listed.write_text("before", encoding="utf-8")
before = fingerprint_files(root, ["listed.txt"])
listed.write_text("after", encoding="utf-8")
after = fingerprint_files(root, ["listed.txt"])
assert before != after
PY

echo "ALL OK"
