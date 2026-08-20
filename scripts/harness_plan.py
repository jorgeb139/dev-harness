#!/usr/bin/env python3
"""Canonical structured plans, generated projections, and plan lifecycle helpers."""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

from harness_store import (
    atomic_write_json,
    atomic_write_text,
    find_sensitive_patterns,
    load_json,
    locked,
    utc_now,
)


SCHEMA_VERSION = 1
TASK_STATUSES = {"pending", "in_progress", "blocked", "completed"}
PHASE_STATUSES = TASK_STATUSES
GREEN_STATUSES = {"complete", "completed", "green", "passed"}
REQUIRED_PLAN_FIELDS = {
    "schema_version",
    "plan_id",
    "original_scope",
    "approved_scope",
    "phases",
    "impact_analysis",
    "mode_options",
    "history",
}
REQUIRED_TASK_FIELDS = {
    "id",
    "status",
    "owner_role",
    "reviewer_roles",
    "dependencies",
    "acceptance_criteria",
    "test_obligations",
    "evidence",
}
REQUIRED_PHASE_GATES = {"security", "regression", "tests", "objectives"}
REQUIRED_TASK_REVIEWS = ("security", "regression", "tests")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MARKDOWN_SENSITIVE = re.compile(r"([\\`*_{}\[\]<>#+|])")


def _require_object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_id(value: object, label: str) -> str:
    identifier = _require_string(value, label)
    if not SAFE_ID.fullmatch(identifier):
        raise ValueError(f"{label} contains unsupported characters: {identifier!r}")
    return identifier


def _validate_string_list(value: object, label: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "an array" if allow_empty else "a non-empty array"
        raise ValueError(f"{label} must be {qualifier}")
    result = []
    for index, item in enumerate(value):
        result.append(_require_string(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _validate_described_items(value: object, label: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        if isinstance(item, str):
            _require_string(item, item_label)
            continue
        item = _require_object(item, item_label)
        _require_string(item.get("description"), f"{item_label}.description")
        if "status" in item:
            _require_string(item["status"], f"{item_label}.status")
        if "evidence" in item and item["evidence"] is not None:
            _validate_content(item["evidence"], f"{item_label}.evidence")
        if "command" in item:
            _require_string(item["command"], f"{item_label}.command")


def _validate_content(value: object, label: str) -> None:
    if isinstance(value, str):
        _require_string(value, label)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_content(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _require_string(key, f"{label} key")
            _validate_content(item, f"{label}.{key}")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must not contain non-finite numbers")
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise ValueError(f"{label} contains unsupported content")


def _validate_scope(value: object, label: str) -> None:
    if isinstance(value, str):
        _require_string(value, label)
        return
    if isinstance(value, dict):
        if not value:
            raise ValueError(f"{label} must not be empty")
        _validate_content(value, label)
        return
    _validate_described_items(value, label)


def _status(value: object) -> str | None:
    if isinstance(value, str):
        return value.casefold()
    if isinstance(value, dict):
        status = value.get("status")
        return status.casefold() if isinstance(status, str) else None
    return None


def _validate_mode_options(mode_options: object) -> None:
    mode_options = _require_object(mode_options, "mode_options")
    recommendation = _require_string(
        mode_options.get("recommendation"), "mode_options.recommendation"
    )
    options = _validate_string_list(
        mode_options.get("options"), "mode_options.options", allow_empty=False
    )
    if recommendation not in options:
        raise ValueError("mode_options recommendation must be one of the declared options")
    choice = mode_options.get("choice")
    if choice is not None:
        choice = _require_string(choice, "mode_options.choice")
        if choice not in options:
            raise ValueError("mode_options choice must be one of the declared options")
    estimates = _require_object(mode_options.get("estimates"), "mode_options.estimates")
    if not estimates:
        raise ValueError("mode_options.estimates must not be empty")
    for mode, estimate in estimates.items():
        _require_string(mode, "mode_options.estimates key")
        _require_string(estimate, f"mode_options.estimates.{mode}")
    for field in ("rationale", "models"):
        if field in mode_options:
            _validate_content(mode_options[field], f"mode_options.{field}")


def _validate_history(history: object) -> None:
    if not isinstance(history, list):
        raise ValueError("history must be an array")
    for index, item in enumerate(history):
        item = _require_object(item, f"history[{index}]")
        _require_string(item.get("event"), f"history[{index}].event")
        if "timestamp" in item:
            _require_string(item["timestamp"], f"history[{index}].timestamp")
        if "detail" in item:
            _validate_content(item["detail"], f"history[{index}].detail")


def _validate_phase_validation(value: object, phase_id: str) -> None:
    validation = _require_object(value, f"phase {phase_id} validation")
    missing = sorted(REQUIRED_PHASE_GATES - set(validation))
    if missing:
        raise ValueError(
            f"phase {phase_id} validation missing gates: {', '.join(missing)}"
        )
    for name, evidence in validation.items():
        _require_string(name, f"phase {phase_id} validation key")
        if _status(evidence) is None:
            raise ValueError(
                f"phase {phase_id} validation {name} must include a status"
            )
        _validate_content(evidence, f"phase {phase_id} validation {name}")


def validate_plan(plan: dict) -> None:
    """Validate the complete structured plan without mutating it."""
    plan = _require_object(plan, "plan")
    missing = sorted(REQUIRED_PLAN_FIELDS - set(plan))
    if missing:
        raise ValueError(f"plan missing fields: {', '.join(missing)}")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported plan schema: {plan['schema_version']}")
    _require_id(plan["plan_id"], "plan_id")
    if "title" in plan:
        _require_string(plan["title"], "title")
    _validate_scope(plan["original_scope"], "original_scope")
    _validate_scope(plan["approved_scope"], "approved_scope")
    _validate_content(plan["impact_analysis"], "impact_analysis")
    if not plan["impact_analysis"]:
        raise ValueError("impact_analysis must not be empty")
    if "assumptions" in plan:
        _validate_described_items(plan["assumptions"], "assumptions")
    if "questions" in plan:
        if not isinstance(plan["questions"], list):
            raise ValueError("questions must be an array")
        for index, question in enumerate(plan["questions"]):
            if isinstance(question, str):
                _require_string(question, f"questions[{index}]")
                continue
            question = _require_object(question, f"questions[{index}]")
            _require_string(question.get("text"), f"questions[{index}].text")
            for field in ("status", "answer"):
                if field in question:
                    _require_string(question[field], f"questions[{index}].{field}")
    _validate_mode_options(plan["mode_options"])
    _validate_history(plan["history"])

    phases = plan["phases"]
    if not isinstance(phases, list) or not phases:
        raise ValueError("phases must be a non-empty ordered array")

    phase_ids: set[str] = set()
    tasks: dict[str, dict] = {}
    task_positions: dict[str, int] = {}
    ordered_task_ids: list[str] = []
    for phase_index, phase_value in enumerate(phases):
        phase = _require_object(phase_value, f"phases[{phase_index}]")
        phase_id = _require_id(phase.get("id"), f"phases[{phase_index}].id")
        if phase_id in phase_ids:
            raise ValueError(f"duplicate phase ID: {phase_id}")
        phase_ids.add(phase_id)
        if "title" in phase:
            _require_string(phase["title"], f"phase {phase_id} title")
        if "status" in phase and phase["status"] not in PHASE_STATUSES:
            raise ValueError(f"invalid phase {phase_id} status: {phase['status']}")
        _validate_described_items(phase.get("objectives"), f"phase {phase_id} objectives")
        _validate_phase_validation(phase.get("validation"), phase_id)

        phase_tasks = phase.get("tasks")
        if not isinstance(phase_tasks, list) or not phase_tasks:
            raise ValueError(f"phase {phase_id} tasks must be a non-empty ordered array")
        for task_offset, task_value in enumerate(phase_tasks):
            task = _require_object(task_value, f"phase {phase_id} tasks[{task_offset}]")
            missing_task_fields = sorted(REQUIRED_TASK_FIELDS - set(task))
            if missing_task_fields:
                raise ValueError(
                    f"task in phase {phase_id} missing fields: {', '.join(missing_task_fields)}"
                )
            task_id = _require_id(task["id"], f"phase {phase_id} task ID")
            if task_id in tasks:
                raise ValueError(f"duplicate task ID: {task_id}")
            if "title" in task:
                _require_string(task["title"], f"task {task_id} title")
            if task["status"] not in TASK_STATUSES:
                raise ValueError(f"invalid task {task_id} status: {task['status']}")
            _require_string(task["owner_role"], f"task {task_id} owner_role")
            _validate_string_list(
                task["reviewer_roles"], f"task {task_id} reviewer_roles", allow_empty=False
            )
            _validate_string_list(
                task["dependencies"], f"task {task_id} dependencies", allow_empty=True
            )
            _validate_described_items(
                task["acceptance_criteria"], f"task {task_id} acceptance_criteria"
            )
            _validate_described_items(
                task["test_obligations"], f"task {task_id} test_obligations"
            )
            _validate_content(task["evidence"], f"task {task_id} evidence")
            if not isinstance(task["evidence"], dict):
                raise ValueError(f"task {task_id} evidence must be an object")
            tasks[task_id] = task
            task_positions[task_id] = len(ordered_task_ids)
            ordered_task_ids.append(task_id)

    for task_id in ordered_task_ids:
        for dependency in tasks[task_id]["dependencies"]:
            if dependency not in tasks:
                raise ValueError(f"task {task_id} has unknown dependency task ID: {dependency}")
            if task_positions[dependency] >= task_positions[task_id]:
                raise ValueError(
                    f"task {task_id} dependency must precede it in plan order: {dependency}"
                )


def load_plan(path: Path) -> dict:
    """Load and validate the canonical JSON plan at *path*."""
    path = Path(path)
    try:
        plan = load_json(path)
    except ValueError as exc:
        if not path.exists():
            raise ValueError(f"plan file not found: {path}") from exc
        if str(exc).startswith("malformed JSON:"):
            raise ValueError(f"malformed plan JSON: {path}") from exc
        raise
    validate_plan(plan)
    return plan


def task_index(plan: dict) -> dict[str, dict]:
    """Return tasks in canonical phase/task order, indexed by stable task ID."""
    validate_plan(plan)
    return {
        task["id"]: task
        for phase in plan["phases"]
        for task in phase["tasks"]
    }


def _markdown_text(value: object) -> str:
    text = " ".join(str(value).split())
    return MARKDOWN_SENSITIVE.sub(r"\\\1", text)


def _description(item: object) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("description", item.get("text", "")))
    return str(item)


def _is_complete(item: object) -> bool:
    return _status(item) in GREEN_STATUSES


def _render_described_items(items: list, *, default_checked: bool = False) -> list[str]:
    lines = []
    for item in items:
        checked = _is_complete(item) or (default_checked and isinstance(item, str))
        lines.append(f"- [{'x' if checked else ' '}] {_markdown_text(_description(item))}")
        if isinstance(item, dict):
            if item.get("command"):
                lines.append(f"  - Command: `{_markdown_text(item['command'])}`")
            if item.get("evidence"):
                lines.append(f"  - Evidence: {_markdown_text(item['evidence'])}")
    return lines


def _render_value(value: object, indent: str = "") -> list[str]:
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            label = _markdown_text(str(key).replace("_", " ").title())
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}- **{label}:**")
                lines.extend(_render_value(item, indent + "  "))
            else:
                lines.append(f"{indent}- **{label}:** {_markdown_text(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.extend(_render_value(item, indent + "  "))
            else:
                lines.append(f"{indent}- {_markdown_text(item)}")
        return lines or [f"{indent}- None"]
    return [f"{indent}- {_markdown_text(value)}"]


def _phase_for_task(plan: dict, task_id: str) -> str:
    for phase in plan["phases"]:
        if any(task["id"] == task_id for task in phase["tasks"]):
            return phase["id"]
    raise ValueError(f"unknown current task ID: {task_id}")


def _current_pointer(plan: dict, state: dict | None) -> tuple[str, str]:
    tasks = task_index(plan)
    if state is not None:
        state = _require_object(state, "state")
        if state.get("plan_id") != plan["plan_id"]:
            raise ValueError("state plan_id does not match plan")
        task_id = _require_string(state.get("task"), "state task")
        if task_id not in tasks:
            raise ValueError(f"unknown current task ID: {task_id}")
        phase_id = _phase_for_task(plan, task_id)
        if str(state.get("phase")) != phase_id:
            raise ValueError(
                f"state phase {state.get('phase')!r} does not contain task {task_id}"
            )
        return phase_id, task_id
    for desired_status in ("in_progress", "pending", "blocked", "completed"):
        for phase in plan["phases"]:
            for task in phase["tasks"]:
                if task["status"] == desired_status:
                    return phase["id"], task["id"]
    raise ValueError("plan has no current task")


def render_markdown(plan: dict, state: dict | None) -> str:
    """Render the canonical plan and optional execution state as generated Markdown."""
    validate_plan(plan)
    current_phase, current_task = _current_pointer(plan, state)
    title = _markdown_text(plan.get("title", plan["plan_id"]))
    mode = plan["mode_options"]
    lines = [
        "<!-- GENERATED FILE: edit .harness/plan.json and execution state, not this file. -->",
        "",
        f"# Plan: {title}",
        "",
        f"- **Plan ID:** `{plan['plan_id']}`",
        f"- **Schema version:** `{plan['schema_version']}`",
        f"- **Current task:** ► Phase {current_phase}, task {current_task}",
        f"- **Mode recommendation:** {_markdown_text(mode['recommendation'])}",
        f"- **User choice:** {_markdown_text(mode.get('choice') or 'pending')}",
        "",
        "## Mode Decision",
        "",
        "### Estimates",
        "",
    ]
    lines.extend(_render_value(mode["estimates"]))
    if mode.get("rationale"):
        lines.extend(["", "### Rationale", "", _markdown_text(mode["rationale"])])
    lines.extend(["", "## Scope", "", "### Original Scope", ""])
    lines.extend(_render_value(plan["original_scope"]))
    lines.extend(["", "### Approved Scope", ""])
    lines.extend(_render_value(plan["approved_scope"]))
    lines.extend(["", "## Impact Analysis", ""])
    lines.extend(_render_value(plan["impact_analysis"]))

    lines.extend(["", "## Assumptions", ""])
    if plan.get("assumptions"):
        lines.extend(_render_described_items(plan["assumptions"]))
    else:
        lines.append("- None recorded")
    lines.extend(["", "## Open Questions", ""])
    if plan.get("questions"):
        for question in plan["questions"]:
            if isinstance(question, str):
                lines.append(f"- [ ] {_markdown_text(question)}")
                continue
            resolved = question.get("status", "").casefold() in {
                "answered", "closed", "resolved",
            }
            lines.append(
                f"- [{'x' if resolved else ' '}] {_markdown_text(question['text'])}"
            )
            if question.get("answer"):
                lines.append(f"  - Answer: {_markdown_text(question['answer'])}")
    else:
        lines.append("- None recorded")

    lines.extend(["", "## Phases"])
    for phase in plan["phases"]:
        phase_title = _markdown_text(phase.get("title", phase["id"]))
        lines.extend([
            "",
            f"### Phase {phase['id']}: {phase_title}",
            "",
            f"- Status: `{phase.get('status', 'pending')}`",
            "",
            "#### Objectives",
            "",
        ])
        lines.extend(
            _render_described_items(
                phase["objectives"],
                default_checked=phase.get("status") == "completed",
            )
        )
        lines.extend(["", "#### Tasks", ""])
        for task in phase["tasks"]:
            checked = task["status"] == "completed"
            task_title = _markdown_text(task.get("title", task["id"]))
            current = " **(current)**" if task["id"] == current_task else ""
            lines.extend([
                f"- [{'x' if checked else ' '}] `{task['id']}` {task_title}{current}",
                f"  - Status: `{task['status']}`",
                f"  - Owner role: `{_markdown_text(task['owner_role'])}`",
                "  - Reviewer roles: " + ", ".join(
                    f"`{_markdown_text(role)}`" for role in task["reviewer_roles"]
                ),
                "  - Dependencies: " + (
                    ", ".join(f"`{dependency}`" for dependency in task["dependencies"])
                    or "None"
                ),
                "  - Acceptance criteria:",
            ])
            lines.extend(
                f"    {line}" for line in _render_described_items(
                    task["acceptance_criteria"], default_checked=checked
                )
            )
            lines.append("  - Test obligations:")
            lines.extend(
                f"    {line}" for line in _render_described_items(
                    task["test_obligations"], default_checked=checked
                )
            )
            lines.append("  - Evidence:")
            if task["evidence"]:
                lines.extend(f"    {line}" for line in _render_value(task["evidence"]))
            else:
                lines.append("    - None recorded")
            lines.append("  - Review status:")
            for review in task["reviewer_roles"]:
                review_key = _review_key(review)
                status = _status(_review_evidence(task["evidence"], review_key)) or "missing"
                lines.append(
                    f"    - [{'x' if status in GREEN_STATUSES else ' '}] "
                    f"{_markdown_text(review)}: `{status}`"
                )
        lines.extend(["", "#### Phase Validation", ""])
        for gate, evidence in phase["validation"].items():
            gate_status = _status(evidence) or "missing"
            lines.append(
                f"- [{'x' if gate_status in GREEN_STATUSES else ' '}] "
                f"{_markdown_text(gate.replace('_', ' ').title())}: `{gate_status}`"
            )

    lines.extend(["", "## Change History", ""])
    if plan["history"]:
        for item in plan["history"]:
            timestamp = _markdown_text(item.get("timestamp", "unknown"))
            detail = _markdown_text(item.get("detail", ""))
            suffix = f" {detail}" if detail else ""
            lines.append(f"- `{timestamp}` `{_markdown_text(item['event'])}`{suffix}")
    else:
        lines.append("- None recorded")
    return "\n".join(lines) + "\n"


def _validate_mode_decision(plan: dict, decision: dict) -> dict:
    decision = _require_object(decision, "mode decision")
    required = {"recommendation", "choice", "estimates"}
    missing = sorted(required - set(decision))
    if missing:
        raise ValueError(f"mode decision missing fields: {', '.join(missing)}")
    unexpected = sorted(set(decision) - required - {"rationale", "models"})
    if unexpected:
        raise ValueError(f"mode decision has unexpected fields: {', '.join(unexpected)}")
    recommendation = _require_string(decision["recommendation"], "mode recommendation")
    choice = _require_string(decision["choice"], "mode choice")
    options = plan["mode_options"]["options"]
    if recommendation not in options:
        raise ValueError("mode recommendation must be one of the declared options")
    if choice not in options:
        raise ValueError("mode choice must be one of the declared options")
    estimates = _require_object(decision["estimates"], "mode estimates")
    if not estimates:
        raise ValueError("mode estimates must not be empty")
    for mode, estimate in estimates.items():
        _require_string(mode, "mode estimates key")
        _require_string(estimate, f"mode estimate {mode}")
    normalized = copy.deepcopy(decision)
    for field in ("rationale", "models"):
        if field in normalized:
            _validate_content(normalized[field], f"mode decision {field}")
    return normalized


def record_mode_decision(
    plan_path: Path,
    state_path: Path,
    decision: dict,
) -> None:
    """Persist the user-owned mode decision in both plan and execution state."""
    plan_path = Path(plan_path)
    state_path = Path(state_path)
    with locked(plan_path):
        with locked(state_path):
            plan = load_plan(plan_path)
            state = load_json(state_path)
            from harness_state import validate_state

            validate_state(state)
            if state["plan_id"] != plan["plan_id"]:
                raise ValueError("state plan_id does not match plan")
            normalized = _validate_mode_decision(plan, decision)
            timestamp = utc_now()
            updated_plan = copy.deepcopy(plan)
            updated_state = copy.deepcopy(state)
            updated_plan["mode_options"].update({
                "recommendation": normalized["recommendation"],
                "choice": normalized["choice"],
                "estimates": normalized["estimates"],
            })
            for field in ("rationale", "models"):
                if field in normalized:
                    updated_plan["mode_options"][field] = normalized[field]
            updated_plan["history"].append({
                "event": "mode_decision",
                "timestamp": timestamp,
                "detail": f"choice={normalized['choice']}",
            })
            updated_state["mode_decision"] = normalized
            updated_state["selected_mode"] = normalized["choice"]
            updated_state["token_estimates"] = normalized["estimates"]
            updated_state["updated_at"] = timestamp
            updated_state["history"].append({
                "event": "mode_decision",
                "timestamp": timestamp,
                "detail": f"choice={normalized['choice']}",
            })
            validate_plan(updated_plan)
            validate_state(updated_state)
            atomic_write_json(plan_path, updated_plan)
            atomic_write_json(state_path, updated_state)


def _review_key(role: str) -> str:
    normalized = role.casefold().replace("_", "-").replace(" ", "-")
    if "security" in normalized:
        return "security"
    if "regression" in normalized:
        return "regression"
    if normalized.startswith("test"):
        return "tests"
    return role


def _review_evidence(evidence: dict, review: str) -> object:
    if review == "tests":
        return evidence.get("tests", evidence.get("test"))
    return evidence.get(review)


def _validate_completed_task_evidence(task: dict) -> None:
    checkpoint = task["evidence"].get("implementation_checkpoint")
    if not checkpoint:
        raise ValueError(
            f"plan is incomplete; task {task['id']} lacks implementation checkpoint evidence"
        )
    if isinstance(checkpoint, dict) and _status(checkpoint) not in GREEN_STATUSES:
        raise ValueError(
            f"plan is incomplete; task {task['id']} implementation checkpoint is not green"
        )
    reviews = list(REQUIRED_TASK_REVIEWS)
    for role in task["reviewer_roles"]:
        review = _review_key(role)
        if review not in reviews:
            reviews.append(review)
    for review in reviews:
        if _status(_review_evidence(task["evidence"], review)) not in GREEN_STATUSES:
            raise ValueError(
                f"plan is incomplete; task {task['id']} {review} review evidence is not green"
            )


def _ensure_complete_for_archive(plan: dict, state: dict) -> None:
    incomplete_tasks = [
        task["id"]
        for phase in plan["phases"]
        for task in phase["tasks"]
        if task["status"] != "completed"
    ]
    if incomplete_tasks:
        raise ValueError(f"plan is incomplete; tasks not completed: {', '.join(incomplete_tasks)}")
    for phase in plan["phases"]:
        for task in phase["tasks"]:
            _validate_completed_task_evidence(task)
    incomplete_phases = []
    for phase in plan["phases"]:
        if phase.get("status", "completed") != "completed":
            incomplete_phases.append(phase["id"])
            continue
        if any(_status(value) not in GREEN_STATUSES for value in phase["validation"].values()):
            incomplete_phases.append(phase["id"])
    if incomplete_phases:
        raise ValueError(
            f"plan is incomplete; phase validation not green: {', '.join(incomplete_phases)}"
        )
    from harness_state import validate_state

    validate_state(state)
    if state["plan_id"] != plan["plan_id"]:
        raise ValueError("state plan_id does not match plan")
    if state["status"] != "completed":
        raise ValueError("plan is incomplete; execution state is not completed")
    if state["blockers"]:
        raise ValueError("plan is incomplete; execution state has blockers")


def _archive_evidence(plan: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan["plan_id"],
        "tasks": {
            task["id"]: copy.deepcopy(task["evidence"])
            for phase in plan["phases"]
            for task in phase["tasks"]
        },
        "phase_validation": {
            phase["id"]: copy.deepcopy(phase["validation"])
            for phase in plan["phases"]
        },
    }


def _matching_active_pointer(path: Path, plan_id: str, label: str) -> bool:
    if not path.exists():
        return False
    value = load_json(path)
    if value.get("plan_id") != plan_id:
        raise ValueError(f"refusing to remove {label} for a different plan")
    return True


def archive_plan(root: Path, plan: dict, state: dict, handoff: str) -> Path:
    """Archive a completed plan and remove matching canonical active pointers."""
    root = Path(root)
    validate_plan(plan)
    _ensure_complete_for_archive(plan, state)
    _require_string(handoff, "handoff")
    evidence = _archive_evidence(plan)
    handoff_metadata = {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan["plan_id"],
        "content": handoff,
    }
    sensitive = find_sensitive_patterns(
        json.dumps(
            {"plan": plan, "state": state, "handoff": handoff_metadata, "evidence": evidence},
            sort_keys=True,
        )
    )
    if sensitive:
        raise ValueError(
            f"refusing to archive sensitive plan content: {', '.join(sensitive)}"
        )

    history_dir = root / "docs" / "plans" / "history"
    archive_path = history_dir / f"{plan['plan_id']}.md"
    artifacts = {
        archive_path: render_markdown(plan, state) + "\n## Final Handoff\n\n" + _markdown_text(handoff) + "\n",
        history_dir / f"{plan['plan_id']}.plan.json": plan,
        history_dir / f"{plan['plan_id']}.state.json": state,
        history_dir / f"{plan['plan_id']}.handoff.json": handoff_metadata,
        history_dir / f"{plan['plan_id']}.evidence.json": evidence,
    }
    active_plan = root / ".harness" / "plan.json"
    active_state = root / ".harness" / "execution-state.json"
    with locked(active_plan):
        with locked(active_state):
            with locked(archive_path):
                remove_active_plan = _matching_active_pointer(
                    active_plan, plan["plan_id"], "active plan"
                )
                remove_active_state = _matching_active_pointer(
                    active_state, plan["plan_id"], "active state"
                )
                existing = [str(path) for path in artifacts if path.exists()]
                if existing:
                    raise ValueError(f"plan archive already exists: {', '.join(existing)}")
                for path, content in artifacts.items():
                    if isinstance(content, str):
                        atomic_write_text(path, content)
                    else:
                        atomic_write_json(path, content)

                if remove_active_plan:
                    active_plan.unlink()
                if remove_active_state:
                    active_state.unlink()
                if remove_active_plan or remove_active_state:
                    for pointer in (
                        root / "docs" / "plans" / "ACTIVE-PLAN.md",
                        root / "docs" / "plans" / "ACTIVE-PLAN.HANDOFF.md",
                        root / "docs" / "plans" / "ACTIVE-PLAN.state.json",
                    ):
                        if pointer.exists():
                            pointer.unlink()
    return archive_path


def _path_argument(parser: argparse.ArgumentParser, flag: str, default: str) -> None:
    parser.add_argument(flag, type=Path, default=Path(default))


def command_validate(args: argparse.Namespace) -> None:
    load_plan(args.plan_json)
    print("plan: valid")


def command_render(args: argparse.Namespace) -> None:
    plan = load_plan(args.plan_json)
    state = load_json(args.state_json) if args.state_json.exists() else None
    atomic_write_text(args.output, render_markdown(plan, state))
    print(f"plan: rendered {args.output}")


def command_mode(args: argparse.Namespace) -> None:
    if args.decision_json:
        decision = load_json(args.decision_json)
    else:
        missing = [
            name
            for name, value in (
                ("--recommendation", args.recommendation),
                ("--choice", args.choice),
                ("--single-estimate", args.single_estimate),
                ("--mixed-estimate", args.mixed_estimate),
                ("--multi-estimate", args.multi_estimate),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"mode requires {', '.join(missing)} or --decision-json")
        decision = {
            "recommendation": args.recommendation,
            "choice": args.choice,
            "estimates": {
                "single_agent": args.single_estimate,
                "mixed": args.mixed_estimate,
                "multi_agent": args.multi_estimate,
            },
        }
        if args.rationale:
            decision["rationale"] = args.rationale
    record_mode_decision(args.plan_json, args.state_json, decision)
    print(f"plan: mode recorded choice={decision['choice']}")


def command_archive(args: argparse.Namespace) -> None:
    plan = load_plan(args.plan_json)
    state = load_json(args.state_json)
    try:
        handoff = args.handoff_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"handoff file not found: {args.handoff_file}") from exc
    path = archive_plan(args.root, plan, state, handoff)
    print(f"plan: archived {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    _path_argument(validate, "--plan-json", ".harness/plan.json")
    validate.set_defaults(handler=command_validate)
    render = commands.add_parser("render")
    _path_argument(render, "--plan-json", ".harness/plan.json")
    _path_argument(render, "--state-json", ".harness/execution-state.json")
    _path_argument(render, "--output", "docs/plans/ACTIVE-PLAN.md")
    render.set_defaults(handler=command_render)
    mode = commands.add_parser("mode")
    _path_argument(mode, "--plan-json", ".harness/plan.json")
    _path_argument(mode, "--state-json", ".harness/execution-state.json")
    mode.add_argument("--decision-json", type=Path)
    mode.add_argument("--recommendation")
    mode.add_argument("--choice")
    mode.add_argument("--single-estimate")
    mode.add_argument("--mixed-estimate")
    mode.add_argument("--multi-estimate")
    mode.add_argument("--rationale")
    mode.set_defaults(handler=command_mode)
    archive = commands.add_parser("archive")
    archive.add_argument("--root", type=Path, default=Path("."))
    _path_argument(archive, "--plan-json", ".harness/plan.json")
    _path_argument(archive, "--state-json", ".harness/execution-state.json")
    _path_argument(archive, "--handoff-file", "docs/plans/ACTIVE-PLAN.HANDOFF.md")
    archive.set_defaults(handler=command_archive)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["plan"]:
        arguments = arguments[1:]
    args = build_parser().parse_args(arguments)
    try:
        args.handler(args)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
