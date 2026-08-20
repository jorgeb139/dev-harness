#!/usr/bin/env python3
"""Portable execution state machine for dev-harness plans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness_store import atomic_write_json, atomic_write_text, load_json, locked, utc_now


SCHEMA_VERSION = 1
STATUSES = {"pending", "in_progress", "blocked", "completed"}
TRANSITIONS = {
    "pending": {"in_progress"},
    "in_progress": {"blocked", "completed"},
    "blocked": {"in_progress"},
    "completed": set(),
}


def now():
    return utc_now()


def paths(args):
    return Path(args.state_file), Path(args.handoff_file)


def load_state(state_path):
    try:
        value = load_json(state_path)
    except ValueError as exc:
        if not state_path.exists():
            raise ValueError(f"state file not found: {state_path}") from exc
        if str(exc).startswith("malformed JSON:"):
            raise ValueError(f"malformed state JSON: {state_path}") from exc
        raise
    validate_state(value)
    return value


def validate_state(value):
    if not isinstance(value, dict):
        raise ValueError("state must be a JSON object")
    required = {
        "schema_version", "plan_id", "plan_file", "status", "phase", "task",
        "owner", "branch", "last_verified_commit", "next_action", "evidence",
        "blockers", "updated_at", "history",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"state missing fields: {', '.join(missing)}")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported state schema: {value['schema_version']}")
    if value["status"] not in STATUSES:
        raise ValueError(f"invalid status: {value['status']}")
    if not isinstance(value["phase"], int) or value["phase"] < 1:
        raise ValueError("phase must be a positive integer")
    for field in ("plan_id", "plan_file", "task", "owner", "branch", "next_action"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not isinstance(value["evidence"], list) or not isinstance(value["blockers"], list):
        raise ValueError("evidence and blockers must be arrays")
    if not isinstance(value["history"], list) or not value["history"]:
        raise ValueError("history must be a non-empty array")
    if value["status"] == "completed" and not value["last_verified_commit"]:
        raise ValueError("completed state requires last_verified_commit")


def handoff_markdown(value):
    lines = [
        f"# Handoff: {value['plan_id']}", "",
        f"- Status: `{value['status']}`", f"- Phase: `{value['phase']}`",
        f"- Task: `{value['task']}`", f"- Owner: `{value['owner']}`",
        f"- Branch: `{value['branch']}`",
        f"- Last verified commit: `{value['last_verified_commit'] or 'none'}`",
        f"- Updated: `{value['updated_at']}`", "", "## Next action", "",
        value["next_action"], "", "## Blockers", "",
    ]
    lines.extend(f"- {item}" for item in value["blockers"] or ["None"])
    lines.extend(["", "## Evidence", ""])
    if value["evidence"]:
        for item in value["evidence"]:
            lines.append(
                f"- `{item.get('timestamp', 'unknown')}`: "
                f"{item.get('result', 'no result')} "
                f"(command: `{item.get('test_command', 'none')}`, "
                f"commit: `{item.get('commit', 'none')}`)"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Recent history", ""])
    for item in value["history"][-10:]:
        detail = item.get("detail", "")
        lines.append(f"- `{item.get('timestamp', 'unknown')}` `{item['event']}` {detail}".rstrip())
    return "\n".join(lines) + "\n"


def save_state(state_path, handoff_path, value):
    validate_state(value)
    atomic_write_json(state_path, value)
    atomic_write_text(handoff_path, handoff_markdown(value))


def event(value, name, detail=""):
    value["updated_at"] = now()
    value["history"].append({"event": name, "detail": detail, "timestamp": value["updated_at"]})


def transition(value, target):
    current = value["status"]
    if target not in TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current} -> {target}")
    value["status"] = target


def mutate(args, operation):
    state_path, handoff_path = paths(args)
    with locked(state_path):
        value = load_state(state_path)
        operation(value)
        save_state(state_path, handoff_path, value)
    print(f"state: {value['status']} task={value['task']}")


def command_init(args):
    state_path, handoff_path = paths(args)
    if state_path.exists():
        raise ValueError(f"state already exists: {state_path}")
    value = {
        "schema_version": SCHEMA_VERSION, "plan_id": args.plan_id,
        "plan_file": args.plan_file, "status": "pending", "phase": args.phase,
        "task": args.task, "owner": args.owner, "branch": args.branch,
        "last_verified_commit": "", "next_action": args.next_action,
        "evidence": [], "blockers": [], "updated_at": now(), "history": [],
    }
    event(value, "initialized", f"plan={args.plan_id}")
    save_state(state_path, handoff_path, value)
    print(f"state: pending task={value['task']}")


def command_start(args):
    def operation(value):
        transition(value, "in_progress")
        value["task"] = args.task
        value["next_action"] = args.next_action
        value["blockers"] = []
        event(value, "started", f"task={args.task}")
    mutate(args, operation)


def command_checkpoint(args):
    def operation(value):
        if value["status"] != "in_progress":
            raise ValueError("checkpoint requires in_progress state")
        value["evidence"].append({
            "timestamp": now(), "commit": args.commit,
            "test_command": args.test_command, "result": args.result,
        })
        value["last_verified_commit"] = args.commit
        value["next_action"] = args.next_action
        event(value, "checkpoint", f"commit={args.commit}")
    mutate(args, operation)


def command_advance(args):
    def operation(value):
        if value["status"] != "in_progress":
            raise ValueError("advance requires in_progress state")
        if not value["evidence"]:
            raise ValueError("advance requires checkpoint evidence")
        previous = f"{value['phase']}.{value['task']}"
        value["phase"] = args.phase
        value["task"] = args.task
        value["next_action"] = args.next_action
        event(value, "advanced", f"from={previous} to={args.phase}.{args.task}")
    mutate(args, operation)


def command_block(args):
    def operation(value):
        transition(value, "blocked")
        value["blockers"].append(args.reason)
        value["next_action"] = args.next_action
        event(value, "blocked", args.reason)
    mutate(args, operation)


def command_resume(args):
    def operation(value):
        transition(value, "in_progress")
        value["blockers"] = []
        value["next_action"] = args.next_action
        event(value, "resumed", args.next_action)
    mutate(args, operation)


def command_complete(args):
    def operation(value):
        transition(value, "completed")
        value["last_verified_commit"] = args.commit
        value["next_action"] = "plan complete"
        value["evidence"].append({
            "timestamp": now(), "commit": args.commit,
            "test_command": args.test_command, "result": args.result,
        })
        event(value, "completed", f"commit={args.commit}")
    if not args.commit or not args.test_command or not args.result:
        raise ValueError("complete requires --commit, --test-command, and --result")
    mutate(args, operation)


def command_show(args):
    state_path, _ = paths(args)
    value = load_state(state_path)
    if args.json:
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(f"{value['plan_id']}: {value['status']} phase={value['phase']} task={value['task']}")
        print(f"next: {value['next_action']}")


def command_validate(args):
    state_path, _ = paths(args)
    validate_state(load_state(state_path))
    print("state: valid")


def add_common(parser):
    parser.add_argument("--state-file", default="docs/plans/ACTIVE-PLAN.state.json")
    parser.add_argument("--handoff-file", default="docs/plans/ACTIVE-PLAN.HANDOFF.md")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    add_common(init)
    init.add_argument("--plan-id", required=True)
    init.add_argument("--plan-file", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--phase", required=True, type=int)
    init.add_argument("--task", required=True)
    init.add_argument("--next-action", required=True)
    init.set_defaults(handler=command_init)
    start = sub.add_parser("start")
    add_common(start)
    start.add_argument("--task", required=True)
    start.add_argument("--next-action", required=True)
    start.set_defaults(handler=command_start)
    checkpoint = sub.add_parser("checkpoint")
    add_common(checkpoint)
    checkpoint.add_argument("--commit", required=True)
    checkpoint.add_argument("--test-command", required=True)
    checkpoint.add_argument("--result", required=True)
    checkpoint.add_argument("--next-action", required=True)
    checkpoint.set_defaults(handler=command_checkpoint)
    advance = sub.add_parser("advance")
    add_common(advance)
    advance.add_argument("--phase", required=True, type=int)
    advance.add_argument("--task", required=True)
    advance.add_argument("--next-action", required=True)
    advance.set_defaults(handler=command_advance)
    block = sub.add_parser("block")
    add_common(block)
    block.add_argument("--reason", required=True)
    block.add_argument("--next-action", required=True)
    block.set_defaults(handler=command_block)
    resume = sub.add_parser("resume")
    add_common(resume)
    resume.add_argument("--next-action", required=True)
    resume.set_defaults(handler=command_resume)
    complete = sub.add_parser("complete")
    add_common(complete)
    complete.add_argument("--commit", required=True)
    complete.add_argument("--test-command", required=True)
    complete.add_argument("--result", required=True)
    complete.set_defaults(handler=command_complete)
    show = sub.add_parser("show")
    add_common(show)
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=command_show)
    validate = sub.add_parser("validate")
    add_common(validate)
    validate.set_defaults(handler=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0
