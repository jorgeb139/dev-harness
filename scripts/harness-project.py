#!/usr/bin/env python3
"""Portable project identity and generated-context CLI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from harness_context import (  # noqa: E402
    SCHEMA_VERSION,
    build_context_inventory,
    context_fingerprint,
    discover_identity,
    render_context,
    validate_identity,
)
from harness_store import atomic_write_json, atomic_write_text, load_json, locked, utc_now  # noqa: E402
from harness_memory import load_memory, record_correction, record_learning  # noqa: E402


class IdentityMismatch(ValueError):
    """Stored identity does not represent the project currently being inspected."""


def _root() -> Path:
    identity = discover_identity(Path.cwd())
    return Path(identity["root"])


def _identity_path(root: Path) -> Path:
    return root / ".harness" / "project-identity.json"


def _context_path(root: Path) -> Path:
    return root / "PROJECT-CONTEXT.md"


def _load_valid_identity(root: Path) -> dict:
    stored = load_json(_identity_path(root))
    errors = validate_identity(root, stored)
    if errors:
        raise IdentityMismatch("; ".join(errors))
    return stored


def command_identity_init(args: argparse.Namespace) -> None:
    root = _root()
    path = _identity_path(root)
    with locked(path):
        if path.exists():
            raise ValueError(f"project identity already exists: {path}")
        identity = discover_identity(root)
        timestamp = utc_now()
        identity.update({
            "context_fingerprint": context_fingerprint(root),
            "created_at": timestamp,
            "updated_at": timestamp,
        })
        atomic_write_json(path, identity)
    print("identity: initialized")


def command_identity_check(args: argparse.Namespace) -> None:
    _load_valid_identity(_root())
    print("identity: valid")


def _write_context(root: Path, initialize: bool) -> None:
    identity_path = _identity_path(root)
    context_path = _context_path(root)
    with locked(identity_path):
        with locked(context_path):
            stored = _load_valid_identity(root)
            if initialize and context_path.exists():
                raise ValueError(f"project context already exists: {context_path}")
            inventory = build_context_inventory(root)
            if inventory["identity"]["identity_id"] != stored["identity_id"]:
                raise IdentityMismatch("current identity does not match stored identity")
            rendered = render_context(inventory)
            updated = dict(stored)
            updated["context_fingerprint"] = inventory["fingerprint"]
            updated["updated_at"] = utc_now()
            atomic_write_text(context_path, rendered)
            atomic_write_json(identity_path, updated)


def command_context_init(args: argparse.Namespace) -> None:
    _write_context(_root(), initialize=True)
    print("context: initialized")


def command_context_refresh(args: argparse.Namespace) -> None:
    _write_context(_root(), initialize=False)
    print("context: refreshed")


def _context_metadata(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"project context not found: {path}") from exc
    fields = {
        "schema_version": r"^- Schema version: `(?P<value>\d+)`$",
        "identity_id": r"^- Identity ID: `(?P<value>[0-9a-f]{64})`$",
        "fingerprint": r"^- Context fingerprint: `(?P<value>[0-9a-f]{64})`$",
    }
    metadata = {}
    for name, pattern in fields.items():
        match = re.search(pattern, content, flags=re.MULTILINE)
        if not match:
            raise ValueError(f"malformed project context: missing {name}")
        metadata[name] = match.group("value")
    if int(metadata["schema_version"]) != SCHEMA_VERSION:
        raise ValueError(f"unsupported context schema: {metadata['schema_version']}")
    return metadata


def command_context_check(args: argparse.Namespace) -> None:
    root = _root()
    stored = _load_valid_identity(root)
    metadata = _context_metadata(_context_path(root))
    if metadata["identity_id"] != stored["identity_id"]:
        raise IdentityMismatch("project context identity_id does not match stored identity")
    status = "fresh" if metadata["fingerprint"] == context_fingerprint(root) else "stale"
    print(status)


def command_memory_list(args: argparse.Namespace) -> None:
    root = _root()
    _load_valid_identity(root)
    print(json.dumps(load_memory(root), indent=2, sort_keys=True))


def command_memory_always(args: argparse.Namespace) -> None:
    root = _root()
    _load_valid_identity(root)
    entry = record_learning(root, args.text, source="explicit_always", explicit_always=True)
    print(entry["notification"])


def command_memory_correction(args: argparse.Namespace) -> None:
    root = _root()
    _load_valid_identity(root)
    entry = record_correction(root, args.text)
    print(entry.get("notification", f"MEMORY CANDIDATE: {entry['id']}"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_subparsers(dest="resource", required=True)
    identity = group.add_parser("identity")
    identity_commands = identity.add_subparsers(dest="command", required=True)
    identity_commands.add_parser("init").set_defaults(handler=command_identity_init)
    identity_commands.add_parser("check").set_defaults(handler=command_identity_check)
    context = group.add_parser("context")
    context_commands = context.add_subparsers(dest="command", required=True)
    context_commands.add_parser("init").set_defaults(handler=command_context_init)
    context_commands.add_parser("check").set_defaults(handler=command_context_check)
    context_commands.add_parser("refresh").set_defaults(handler=command_context_refresh)
    memory = group.add_parser("memory")
    memory_commands = memory.add_subparsers(dest="command", required=True)
    memory_commands.add_parser("list").set_defaults(handler=command_memory_list)
    always = memory_commands.add_parser("always")
    always.add_argument("--text", required=True)
    always.set_defaults(handler=command_memory_always)
    correction = memory_commands.add_parser("correction")
    correction.add_argument("--text", required=True)
    correction.set_defaults(handler=command_memory_correction)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except IdentityMismatch as exc:
        print(f"ERROR: identity mismatch: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
