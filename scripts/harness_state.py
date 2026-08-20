#!/usr/bin/env python3
"""Portable execution state machine for dev-harness plans."""

from __future__ import annotations

import argparse
import json
import re
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
SAFE_STATE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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
    if type(value["phase"]) is int:
        if value["phase"] < 1:
            raise ValueError("phase must be a positive integer or stable phase ID")
    elif (
        not isinstance(value["phase"], str)
        or not value["phase"].strip()
        or not SAFE_STATE_ID.fullmatch(value["phase"])
    ):
        raise ValueError("phase must be a positive integer or stable phase ID")
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
    with locked(state_path):
        if state_path.exists():
            raise ValueError(f"state already exists: {state_path}")
        value = {
            "schema_version": SCHEMA_VERSION, "plan_id": args.plan_id,
            "plan_file": args.plan_file, "status": "pending", "phase": _phase_value(args.phase),
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
        from harness_plan import load_plan

        plan = load_plan(Path(args.plan_json))
        validate_task_transition(value, plan, str(args.phase), args.task)
        previous = f"{value['phase']}.{value['task']}"
        value["phase"] = _phase_value(args.phase)
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
    parser.add_argument("--plan-json", default=".harness/plan.json")


def _phase_value(value):
    value = str(value)
    if value.isdigit() and value == str(int(value)):
        return int(value)
    return value


def _phase_for_task(plan, task_id):
    for phase in plan["phases"]:
        if any(task["id"] == task_id for task in phase["tasks"]):
            return phase["id"]
    raise ValueError(f"unknown current task ID: {task_id}")


def _evidence_status(evidence):
    if isinstance(evidence, str):
        return evidence.casefold()
    if isinstance(evidence, dict) and isinstance(evidence.get("status"), str):
        return evidence["status"].casefold()
    return None


def _review_key(role):
    normalized = role.casefold().replace("_", "-").replace(" ", "-")
    if "security" in normalized:
        return "security"
    if "regression" in normalized:
        return "regression"
    if normalized.startswith("test"):
        return "tests"
    return role


def _review_evidence(evidence, review):
    if review == "tests":
        return evidence.get("tests", evidence.get("test"))
    return evidence.get(review)


def validate_task_transition(value: dict, plan: dict, target_phase: str, target_task: str) -> None:
    """Fail closed unless the plan permits advancing to the target task."""
    from harness_plan import task_index, validate_plan

    validate_state(value)
    validate_plan(plan)
    if value["plan_id"] != plan["plan_id"]:
        raise ValueError("state plan_id does not match plan")
    tasks = task_index(plan)
    current_task_id = value["task"]
    if current_task_id not in tasks:
        raise ValueError(f"unknown current task ID: {current_task_id}")
    if target_task not in tasks:
        raise ValueError(f"unknown target task ID: {target_task}")
    target_phase = str(target_phase)
    actual_target_phase = _phase_for_task(plan, target_task)
    if target_phase != actual_target_phase:
        raise ValueError(
            f"target task {target_task} belongs to phase {actual_target_phase}, not {target_phase}"
        )
    if target_task == current_task_id:
        raise ValueError("advance target task must differ from the current task")
    incomplete = [
        dependency
        for dependency in tasks[target_task]["dependencies"]
        if tasks[dependency]["status"] != "completed"
    ]
    if incomplete:
        raise ValueError(f"incomplete dependencies: {', '.join(incomplete)}")

    current = tasks[current_task_id]
    if current["status"] != "completed":
        raise ValueError(f"current task {current_task_id} is not completed")
    checkpoint = current["evidence"].get("implementation_checkpoint")
    if not checkpoint:
        raise ValueError("current task requires implementation checkpoint evidence")
    if isinstance(checkpoint, dict):
        checkpoint_status = _evidence_status(checkpoint)
        if checkpoint_status not in {"complete", "completed", "green", "passed"}:
            raise ValueError("implementation checkpoint evidence must be green")

    required_reviews = list(("security", "regression", "tests"))
    for role in current["reviewer_roles"]:
        review_key = _review_key(role)
        if review_key not in required_reviews:
            required_reviews.append(review_key)
    for review in required_reviews:
        if _evidence_status(_review_evidence(current["evidence"], review)) not in {
            "complete", "completed", "green", "passed",
        }:
            label = "test" if review == "tests" else review
            raise ValueError(f"{label} review evidence must be green")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    add_common(init)
    init.add_argument("--plan-id", required=True)
    init.add_argument("--plan-file", required=True)
    init.add_argument("--branch", required=True)
    init.add_argument("--owner", required=True)
    init.add_argument("--phase", required=True)
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
    advance.add_argument("--phase", required=True)
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
