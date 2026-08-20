#!/usr/bin/env python3
"""Canonical structured plans, generated projections, and plan lifecycle helpers."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from harness_store import atomic_write_text, find_sensitive_patterns, load_json, utc_now


SCHEMA_VERSION = 1
TASK_STATUSES = {"pending", "in_progress", "blocked", "completed"}
PHASE_STATUSES = TASK_STATUSES
ITEM_STATUSES = {"pending", "in_progress", "blocked", "complete", "completed", "green", "passed"}
GREEN_STATUSES = {"complete", "completed", "green", "passed"}
REQUIRED_PLAN_FIELDS = {
    "schema_version", "plan_id", "original_scope", "approved_scope", "phases",
    "impact_analysis", "mode_options", "history",
}
REQUIRED_TASK_FIELDS = {
    "id", "status", "owner_role", "reviewer_roles", "dependencies",
    "acceptance_criteria", "test_obligations", "evidence",
}
REQUIRED_PHASE_GATES = {"security", "regression", "tests", "objectives"}
REQUIRED_TASK_REVIEWS = ("security", "regression", "tests")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PROSE_SENSITIVE = re.compile(r"([\\`*_{}\[\]<>#+|])")


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


def _has_evidence(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return bool(value)


def _validate_string_list(value: object, label: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "an array" if allow_empty else "a non-empty array"
        raise ValueError(f"{label} must be {qualifier}")
    result = [_require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must not contain duplicates")
    return result


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


def _validate_text_collection(value: object, label: str) -> None:
    if isinstance(value, str):
        _require_string(value, label)
        return
    if isinstance(value, dict):
        if not value:
            raise ValueError(f"{label} must not be empty")
        _validate_content(value, label)
        return
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    for index, item in enumerate(value):
        _validate_content(item, f"{label}[{index}]")


def _status(value: object) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("status"), str):
        return value["status"].casefold()
    return None


def _validate_completion_items(
    value: object,
    label: str,
    *,
    require_command: bool = False,
) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    for index, raw_item in enumerate(value):
        item_label = f"{label}[{index}]"
        item = _require_object(raw_item, item_label)
        required = {"description", "status", "evidence"}
        if require_command:
            required.add("command")
        missing = sorted(required - set(item))
        if missing:
            raise ValueError(f"{item_label} missing fields: {', '.join(missing)}")
        _require_string(item["description"], f"{item_label}.description")
        status = _require_string(item["status"], f"{item_label}.status").casefold()
        if status not in ITEM_STATUSES:
            raise ValueError(f"{item_label}.status is invalid: {status}")
        _validate_content(item["evidence"], f"{item_label}.evidence")
        if status in GREEN_STATUSES and not _has_evidence(item["evidence"]):
            raise ValueError(f"{item_label}.evidence is required when complete")
        if require_command:
            _require_string(item["command"], f"{item_label}.command")


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
    missing_estimates = [mode for mode in options if mode not in estimates]
    extra_estimates = sorted(set(estimates) - set(options))
    if missing_estimates:
        raise ValueError(f"mode_options missing estimates: {', '.join(missing_estimates)}")
    if extra_estimates:
        raise ValueError(f"mode_options has estimates for undeclared modes: {', '.join(extra_estimates)}")
    for mode in options:
        _require_string(estimates[mode], f"mode_options.estimates.{mode}")
    for field in ("rationale", "models"):
        if field in mode_options:
            _validate_content(mode_options[field], f"mode_options.{field}")


def _validate_history(history: object) -> None:
    if not isinstance(history, list):
        raise ValueError("history must be an array")
    for index, raw_item in enumerate(history):
        item = _require_object(raw_item, f"history[{index}]")
        _require_string(item.get("event"), f"history[{index}].event")
        if "timestamp" in item:
            _require_string(item["timestamp"], f"history[{index}].timestamp")
        if "detail" in item:
            _validate_content(item["detail"], f"history[{index}].detail")


def _validate_phase_validation(value: object, phase_id: str) -> None:
    validation = _require_object(value, f"phase {phase_id} validation")
    missing = sorted(REQUIRED_PHASE_GATES - set(validation))
    if missing:
        raise ValueError(f"phase {phase_id} validation missing gates: {', '.join(missing)}")
    for name, raw_evidence in validation.items():
        _require_string(name, f"phase {phase_id} validation key")
        evidence = _require_object(raw_evidence, f"phase {phase_id} validation {name}")
        missing_fields = sorted({"status", "evidence"} - set(evidence))
        if missing_fields:
            raise ValueError(
                f"phase {phase_id} validation {name} missing fields: {', '.join(missing_fields)}"
            )
        status = _require_string(
            evidence["status"], f"phase {phase_id} validation {name}.status"
        ).casefold()
        if status not in ITEM_STATUSES:
            raise ValueError(f"phase {phase_id} validation {name} status is invalid")
        _validate_content(evidence["evidence"], f"phase {phase_id} validation {name}.evidence")
        if status in GREEN_STATUSES and not _has_evidence(evidence["evidence"]):
            raise ValueError(f"phase {phase_id} validation {name} requires evidence")
        for field, content in evidence.items():
            if field not in {"status", "evidence"}:
                _validate_content(content, f"phase {phase_id} validation {name}.{field}")


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
    _validate_text_collection(plan["original_scope"], "original_scope")
    _validate_text_collection(plan["approved_scope"], "approved_scope")
    _validate_content(plan["impact_analysis"], "impact_analysis")
    if not plan["impact_analysis"]:
        raise ValueError("impact_analysis must not be empty")
    if "assumptions" in plan:
        _validate_text_collection(plan["assumptions"], "assumptions")
    if "questions" in plan:
        if not isinstance(plan["questions"], list):
            raise ValueError("questions must be an array")
        for index, raw_question in enumerate(plan["questions"]):
            if isinstance(raw_question, str):
                _require_string(raw_question, f"questions[{index}]")
                continue
            question = _require_object(raw_question, f"questions[{index}]")
            _require_string(question.get("text"), f"questions[{index}].text")
            for field, value in question.items():
                if field != "text":
                    _validate_content(value, f"questions[{index}].{field}")
    _validate_mode_options(plan["mode_options"])
    _validate_history(plan["history"])

    phases = plan["phases"]
    if not isinstance(phases, list) or not phases:
        raise ValueError("phases must be a non-empty ordered array")
    phase_ids: set[str] = set()
    tasks: dict[str, dict] = {}
    task_positions: dict[str, int] = {}
    ordered_task_ids: list[str] = []
    for phase_index, raw_phase in enumerate(phases):
        phase = _require_object(raw_phase, f"phases[{phase_index}]")
        phase_id = _require_id(phase.get("id"), f"phases[{phase_index}].id")
        if phase_id in phase_ids:
            raise ValueError(f"duplicate phase ID: {phase_id}")
        phase_ids.add(phase_id)
        if "title" in phase:
            _require_string(phase["title"], f"phase {phase_id} title")
        if "status" in phase and phase["status"] not in PHASE_STATUSES:
            raise ValueError(f"invalid phase {phase_id} status: {phase['status']}")
        _validate_completion_items(phase.get("objectives"), f"phase {phase_id} objectives")
        _validate_phase_validation(phase.get("validation"), phase_id)
        phase_tasks = phase.get("tasks")
        if not isinstance(phase_tasks, list) or not phase_tasks:
            raise ValueError(f"phase {phase_id} tasks must be a non-empty ordered array")
        for task_offset, raw_task in enumerate(phase_tasks):
            task = _require_object(raw_task, f"phase {phase_id} tasks[{task_offset}]")
            missing_task = sorted(REQUIRED_TASK_FIELDS - set(task))
            if missing_task:
                raise ValueError(
                    f"task in phase {phase_id} missing fields: {', '.join(missing_task)}"
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
            _validate_completion_items(
                task["acceptance_criteria"], f"task {task_id} acceptance_criteria"
            )
            _validate_completion_items(
                task["test_obligations"], f"task {task_id} test_obligations",
                require_command=True,
            )
            if not isinstance(task["evidence"], dict):
                raise ValueError(f"task {task_id} evidence must be an object")
            _validate_content(task["evidence"], f"task {task_id} evidence")
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


def _prose(value: object) -> str:
    text = " ".join(str(value).split())
    return PROSE_SENSITIVE.sub(r"\\\1", text)


def _code_span(value: object) -> str:
    text = " ".join(str(value).split())
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    delimiter = "`" * (max(runs, default=0) + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def _description(item: dict) -> str:
    return str(item["description"])


def _is_complete(item: object) -> bool:
    return _status(item) in GREEN_STATUSES


def _render_completion_items(items: list[dict]) -> list[str]:
    lines = []
    for item in items:
        lines.append(
            f"- [{'x' if _is_complete(item) else ' '}] {_prose(_description(item))}"
        )
        lines.append(f"  - Status: {_code_span(item['status'])}")
        if "command" in item:
            lines.append(f"  - Command: {_code_span(item['command'])}")
        if _has_evidence(item["evidence"]):
            lines.append("  - Evidence:")
            lines.extend(_render_value(item["evidence"], "    "))
        else:
            lines.append("  - Evidence: None recorded")
    return lines


def _render_value(value: object, indent: str = "") -> list[str]:
    if isinstance(value, dict):
        lines = []
        for key in sorted(value):
            item = value[key]
            label = _prose(str(key).replace("_", " ").title())
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}- **{label}:**")
                lines.extend(_render_value(item, indent + "  "))
            elif item is None:
                lines.append(f"{indent}- **{label}:** None")
            else:
                lines.append(f"{indent}- **{label}:** {_prose(item)}")
        return lines or [f"{indent}- None"]
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{indent}-")
                lines.extend(_render_value(item, indent + "  "))
            else:
                lines.append(f"{indent}- {_prose(item)}")
        return lines or [f"{indent}- None"]
    return [f"{indent}- {_prose(value) if value is not None else 'None'}"]


def _phase_for_task(plan: dict, task_id: str) -> str:
    for phase in plan["phases"]:
        if any(task["id"] == task_id for task in phase["tasks"]):
            return phase["id"]
    raise ValueError(f"unknown current task ID: {task_id}")


def _current_pointer(plan: dict, state: dict | None) -> tuple[str, str]:
    tasks = task_index(plan)
    if state is not None:
        from harness_state import validate_state

        validate_state(state)
        if state["plan_id"] != plan["plan_id"]:
            raise ValueError("state plan_id does not match plan")
        task_id = state["task"]
        if task_id not in tasks:
            raise ValueError(f"unknown current task ID: {task_id}")
        phase_id = _phase_for_task(plan, task_id)
        if str(state["phase"]) != phase_id:
            raise ValueError(f"state phase {state['phase']!r} does not contain task {task_id}")
        return phase_id, task_id
    for desired_status in ("in_progress", "pending", "blocked", "completed"):
        for phase in plan["phases"]:
            for task in phase["tasks"]:
                if task["status"] == desired_status:
                    return phase["id"], task["id"]
    raise ValueError("plan has no current task")


def _render_execution_state(state: dict | None) -> list[str]:
    lines = ["", "## Execution State", ""]
    if state is None:
        return lines + ["- None recorded"]
    lines.extend([
        f"- **Execution status:** {_code_span(state['status'])}",
        f"- **Owner:** {_code_span(state['owner'])}",
        f"- **Branch:** {_code_span(state['branch'])}",
        f"- **Last completed task:** {_code_span(state['last_completed_task'] or 'none')}",
        f"- **Last verified commit:** {_code_span(state['last_verified_commit'] or 'none')}",
        f"- **Selected mode:** {_prose(state['selected_mode'] or 'pending')}",
        f"- **Attempt count:** {_code_span(state['attempt_count'])}",
        f"- **Next action:** {_prose(state['next_action'])}",
        f"- **Updated at:** {_code_span(state['updated_at'])}",
        "- **Token estimates:**",
    ])
    lines.extend(_render_value(state["token_estimates"], "  "))
    lines.append("- **Checkpoint metadata:**")
    lines.extend(_render_value(state["checkpoint_metadata"], "  "))
    lines.append("- **Attempt metadata:**")
    lines.extend(_render_value(state["attempt_metadata"], "  "))
    lines.append("- **Blockers:**")
    lines.extend(_render_value(state["blockers"], "  "))
    return lines


def render_markdown(plan: dict, state: dict | None) -> str:
    """Render every accepted plan/state field with context-specific Markdown escaping."""
    validate_plan(plan)
    current_phase, current_task = _current_pointer(plan, state)
    title = _prose(plan.get("title", plan["plan_id"]))
    mode = plan["mode_options"]
    lines = [
        "<!-- GENERATED FILE: edit .harness/plan.json and execution state, not this file. -->",
        "", f"# Plan: {title}", "",
        f"- **Plan ID:** {_code_span(plan['plan_id'])}",
        f"- **Schema version:** {_code_span(plan['schema_version'])}",
        f"- **Current task:** ► Phase {current_phase}, task {current_task}",
        f"- **Mode recommendation:** {_prose(mode['recommendation'])}",
        f"- **User choice:** {_prose(mode.get('choice') or 'pending')}",
    ]
    lines.extend(_render_execution_state(state))
    lines.extend(["", "## Mode Decision", "", "### Declared Options", ""])
    lines.extend(f"- {_code_span(option)}" for option in mode["options"])
    lines.extend(["", "### Estimates", ""])
    lines.extend(_render_value(mode["estimates"]))
    lines.extend(["", "### Models", ""])
    lines.extend(_render_value(mode.get("models", {})))
    if mode.get("rationale"):
        lines.extend(["", "### Rationale", "", _prose(mode["rationale"])])
    lines.extend(["", "## Scope", "", "### Original Scope", ""])
    lines.extend(_render_value(plan["original_scope"]))
    lines.extend(["", "### Approved Scope", ""])
    lines.extend(_render_value(plan["approved_scope"]))
    lines.extend(["", "## Impact Analysis", ""])
    lines.extend(_render_value(plan["impact_analysis"]))
    lines.extend(["", "## Assumptions", ""])
    lines.extend(_render_value(plan.get("assumptions", [])))
    lines.extend(["", "## Open Questions", ""])
    if plan.get("questions"):
        for question in plan["questions"]:
            if isinstance(question, str):
                lines.append(f"- [ ] {_prose(question)}")
                continue
            resolved = str(question.get("status", "")).casefold() in {
                "answered", "closed", "resolved",
            }
            lines.append(f"- [{'x' if resolved else ' '}] {_prose(question['text'])}")
            for field, value in question.items():
                if field != "text":
                    lines.append(f"  - **{_prose(field.title())}:** {_prose(value)}")
    else:
        lines.append("- None recorded")

    lines.extend(["", "## Phases"])
    for phase in plan["phases"]:
        phase_title = _prose(phase.get("title", phase["id"]))
        lines.extend([
            "", f"### Phase {phase['id']}: {phase_title}", "",
            f"- Status: {_code_span(phase.get('status', 'pending'))}",
            "", "#### Objectives", "",
        ])
        lines.extend(_render_completion_items(phase["objectives"]))
        lines.extend(["", "#### Tasks", ""])
        for task in phase["tasks"]:
            checked = task["status"] == "completed"
            task_title = _prose(task.get("title", task["id"]))
            current = " **(current)**" if task["id"] == current_task else ""
            lines.extend([
                f"- [{'x' if checked else ' '}] {_code_span(task['id'])} {task_title}{current}",
                f"  - Status: {_code_span(task['status'])}",
                f"  - Owner role: {_code_span(task['owner_role'])}",
                "  - Reviewer roles: " + ", ".join(
                    _code_span(role) for role in task["reviewer_roles"]
                ),
                "  - Dependencies: " + (
                    ", ".join(_code_span(item) for item in task["dependencies"]) or "None"
                ),
                "  - Acceptance criteria:",
            ])
            lines.extend(f"    {line}" for line in _render_completion_items(
                task["acceptance_criteria"]
            ))
            lines.append("  - Test obligations:")
            lines.extend(f"    {line}" for line in _render_completion_items(
                task["test_obligations"]
            ))
            lines.append("  - Evidence:")
            lines.extend(_render_value(task["evidence"], "    "))
            lines.append("  - Review status:")
            for review in task["reviewer_roles"]:
                review_key = _review_key(review)
                review_status = _status(_review_evidence(task["evidence"], review_key)) or "missing"
                lines.append(
                    f"    - [{'x' if review_status in GREEN_STATUSES else ' '}] "
                    f"{_prose(review)}: {_code_span(review_status)}"
                )
        lines.extend(["", "#### Phase Validation", ""])
        for gate, evidence in phase["validation"].items():
            gate_status = _status(evidence) or "missing"
            lines.append(
                f"- [{'x' if gate_status in GREEN_STATUSES else ' '}] "
                f"{_prose(gate.replace('_', ' ').title())}: {_code_span(gate_status)}"
            )
            lines.extend(_render_value(
                {key: value for key, value in evidence.items() if key != "status"}, "  "
            ))

    lines.extend(["", "## Change History", ""])
    if plan["history"]:
        for item in plan["history"]:
            timestamp = _code_span(item.get("timestamp", "unknown"))
            event = _code_span(item["event"])
            detail = _prose(item.get("detail", ""))
            lines.append(f"- {timestamp} {event}{f' {detail}' if detail else ''}")
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
    options = plan["mode_options"]["options"]
    recommendation = _require_string(decision["recommendation"], "mode recommendation")
    choice = _require_string(decision["choice"], "mode choice")
    if recommendation not in options:
        raise ValueError("mode recommendation must be one of the declared options")
    if choice not in options:
        raise ValueError("mode choice must be one of the declared options")
    estimates = _require_object(decision["estimates"], "mode estimates")
    missing_estimates = [mode for mode in options if mode not in estimates]
    extra_estimates = sorted(set(estimates) - set(options))
    if missing_estimates:
        raise ValueError(f"mode decision missing estimates: {', '.join(missing_estimates)}")
    if extra_estimates:
        raise ValueError(f"mode decision has undeclared estimates: {', '.join(extra_estimates)}")
    for mode in options:
        _require_string(estimates[mode], f"mode estimate {mode}")
    normalized = copy.deepcopy(decision)
    for field in ("rationale", "models"):
        if field in normalized:
            _validate_content(normalized[field], f"mode decision {field}")
    return normalized


def _project_root_for_plan(plan_path: Path) -> Path:
    path = Path(plan_path).resolve()
    if path.parent.name == ".harness":
        return path.parent.parent
    return Path.cwd().resolve()


def _standard_state_candidates(root: Path, requested: Path | None) -> tuple[Path, ...]:
    canonical = root / ".harness/execution-state.json"
    legacy = root / "docs/plans/ACTIVE-PLAN.state.json"
    if requested is None:
        return canonical, legacy
    requested = Path(requested).resolve()
    if requested in {canonical, legacy}:
        return canonical, legacy
    return (requested,)


def record_mode_decision(plan_path: Path, state_path: Path, decision: dict) -> None:
    """Persist plan/state/projection as one recoverable mode-decision transaction."""
    from harness_state import (
        locked_paths, publish_transaction, resolve_execution_state, resume_transaction,
        transaction_manifest_path, validate_state, value_fingerprint,
    )

    plan_path = Path(plan_path).resolve()
    state_path = Path(state_path).resolve()
    root = _project_root_for_plan(plan_path)
    transaction_id = "mode-decision"
    metadata = {
        "operation": "mode-decision",
        "decision": value_fingerprint(decision),
        "plan_path": plan_path.relative_to(root).as_posix(),
    }
    candidates = _standard_state_candidates(root, state_path)
    active_markdown = root / "docs/plans/ACTIVE-PLAN.md"
    lock_targets = list(candidates) + [
        plan_path, active_markdown, transaction_manifest_path(root, transaction_id),
    ]
    with locked_paths(lock_targets):
        if resume_transaction(root, transaction_id, metadata):
            return
        resolution = resolve_execution_state(root, state_path)
        plan = load_plan(plan_path)
        state = load_json(resolution.path)
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
        writes: dict[Path, tuple[str, object]] = {plan_path: ("json", updated_plan)}
        for destination in resolution.write_paths:
            writes[destination] = ("json", updated_state)
        writes[active_markdown] = (
            "text", render_markdown(updated_plan, updated_state),
        )
        publish_transaction(
            root, transaction_id, writes, metadata=metadata,
        )


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


def _validate_green_checkpoint(task: dict) -> None:
    checkpoint = task["evidence"].get("implementation_checkpoint")
    if not isinstance(checkpoint, dict):
        raise ValueError(
            f"plan is incomplete; task {task['id']} implementation checkpoint must be typed"
        )
    required = {"status", "commit", "test_command", "result"}
    missing = sorted(required - set(checkpoint))
    if missing:
        raise ValueError(
            f"plan is incomplete; task {task['id']} checkpoint missing: {', '.join(missing)}"
        )
    if _status(checkpoint) not in GREEN_STATUSES:
        raise ValueError(
            f"plan is incomplete; task {task['id']} implementation checkpoint is not green"
        )
    for field in ("commit", "test_command", "result"):
        if not isinstance(checkpoint[field], str) or not checkpoint[field].strip():
            raise ValueError(
                f"plan is incomplete; task {task['id']} checkpoint {field} is missing"
            )


def _ensure_complete_for_archive(plan: dict, state: dict) -> None:
    from harness_state import validate_state

    validate_plan(plan)
    validate_state(state)
    for phase in plan["phases"]:
        if phase.get("status") != "completed":
            raise ValueError(f"plan is incomplete; phase {phase['id']} is not completed")
        for objective in phase["objectives"]:
            if not _is_complete(objective) or not _has_evidence(objective["evidence"]):
                raise ValueError(f"plan is incomplete; phase {phase['id']} objective is pending")
        for gate_name, gate in phase["validation"].items():
            if not _is_complete(gate) or not _has_evidence(gate["evidence"]):
                raise ValueError(
                    f"plan is incomplete; phase {phase['id']} {gate_name} validation is pending"
                )
        for task in phase["tasks"]:
            if task["status"] != "completed":
                raise ValueError(f"plan is incomplete; task {task['id']} is not completed")
            for criterion in task["acceptance_criteria"]:
                if not _is_complete(criterion) or not _has_evidence(criterion["evidence"]):
                    raise ValueError(
                        f"plan is incomplete; task {task['id']} acceptance criterion is pending"
                    )
            for obligation in task["test_obligations"]:
                if not _is_complete(obligation) or not _has_evidence(obligation["evidence"]):
                    raise ValueError(
                        f"plan is incomplete; task {task['id']} test obligation is pending"
                    )
            _validate_green_checkpoint(task)
            reviews = list(REQUIRED_TASK_REVIEWS)
            for role in task["reviewer_roles"]:
                review = _review_key(role)
                if review not in reviews:
                    reviews.append(review)
            for review in reviews:
                review_value = _review_evidence(task["evidence"], review)
                if _status(review_value) not in GREEN_STATUSES or not _has_evidence(
                    review_value.get("result") if isinstance(review_value, dict) else None
                ):
                    raise ValueError(
                        f"plan is incomplete; task {task['id']} {review} review evidence is not green"
                    )
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
        "completion_items": {
            phase["id"]: {
                "objectives": copy.deepcopy(phase["objectives"]),
                "tasks": {
                    task["id"]: {
                        "acceptance_criteria": copy.deepcopy(task["acceptance_criteria"]),
                        "test_obligations": copy.deepcopy(task["test_obligations"]),
                    }
                    for task in phase["tasks"]
                },
            }
            for phase in plan["phases"]
        },
        "phase_validation": {
            phase["id"]: copy.deepcopy(phase["validation"])
            for phase in plan["phases"]
        },
    }


def _structured_sensitive_patterns(value: object) -> set[str]:
    patterns: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            patterns.update(find_sensitive_patterns(f"{key}=value"))
            if isinstance(item, str):
                patterns.update(find_sensitive_patterns(f"{key}={item}"))
            patterns.update(_structured_sensitive_patterns(item))
    elif isinstance(value, list):
        for item in value:
            patterns.update(_structured_sensitive_patterns(item))
    elif isinstance(value, str):
        patterns.update(find_sensitive_patterns(value))
    return patterns


def _handoff_fingerprint(handoff: str) -> str:
    return hashlib.sha256(handoff.encode("utf-8")).hexdigest()


def archive_plan(root: Path, plan: dict, state: dict, handoff: str) -> Path:
    """Archive only exact locked active snapshots through a resumable transaction."""
    from harness_state import (
        file_fingerprint, locked_paths, publish_transaction, resolve_execution_state,
        resume_transaction, transaction_manifest_path, value_fingerprint,
    )

    root = Path(root).resolve()
    _require_id(plan.get("plan_id") if isinstance(plan, dict) else None, "plan_id")
    _require_string(handoff, "handoff")
    plan_id = plan["plan_id"]
    transaction_id = f"archive-{plan_id}"
    metadata = {
        "operation": "archive",
        "plan": value_fingerprint(plan),
        "state": value_fingerprint(state),
        "handoff": _handoff_fingerprint(handoff),
    }
    history_dir = root / "docs/plans/history"
    archive_path = history_dir / f"{plan_id}.md"
    artifact_paths = (
        archive_path,
        history_dir / f"{plan_id}.plan.json",
        history_dir / f"{plan_id}.state.json",
        history_dir / f"{plan_id}.handoff.json",
        history_dir / f"{plan_id}.evidence.json",
    )
    active_plan_path = root / ".harness/plan.json"
    canonical_state = root / ".harness/execution-state.json"
    legacy_state = root / "docs/plans/ACTIVE-PLAN.state.json"
    active_markdown = root / "docs/plans/ACTIVE-PLAN.md"
    active_handoff = root / "docs/plans/ACTIVE-PLAN.HANDOFF.md"
    lock_targets = [
        active_plan_path, canonical_state, legacy_state, active_markdown, active_handoff,
        *artifact_paths, transaction_manifest_path(root, transaction_id),
    ]
    with locked_paths(lock_targets):
        if resume_transaction(root, transaction_id, metadata):
            return archive_path
        resolution = resolve_execution_state(root, allow_pending=False)
        active_plan = load_plan(active_plan_path)
        active_state = load_json(resolution.path)
        if active_plan != plan:
            raise ValueError("stale archive caller: active plan snapshot changed")
        if active_state != state:
            raise ValueError("stale archive caller: active state snapshot changed")
        _ensure_complete_for_archive(active_plan, active_state)
        structured_patterns = _structured_sensitive_patterns({
            "plan": active_plan,
            "state": active_state,
        })
        handoff_patterns = set(find_sensitive_patterns(handoff))
        sensitive = sorted(structured_patterns | handoff_patterns)
        if sensitive:
            raise ValueError(f"refusing to archive sensitive plan content: {', '.join(sensitive)}")

        expected_markdown = render_markdown(active_plan, active_state)
        if active_markdown.exists() and active_markdown.read_text(encoding="utf-8") != expected_markdown:
            raise ValueError("active Markdown pointer ownership mismatch")
        if active_handoff.exists() and active_handoff.read_text(encoding="utf-8") != handoff:
            raise ValueError("active handoff pointer ownership mismatch")
        for path in artifact_paths:
            if path.exists():
                raise ValueError(f"plan archive already exists: {path}")

        evidence = _archive_evidence(active_plan)
        handoff_metadata = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "content": handoff,
        }
        archive_markdown = (
            expected_markdown + "\n## Final Handoff\n\n" + _prose(handoff) + "\n"
        )
        writes = {
            artifact_paths[0]: ("text", archive_markdown),
            artifact_paths[1]: ("json", active_plan),
            artifact_paths[2]: ("json", active_state),
            artifact_paths[3]: ("json", handoff_metadata),
            artifact_paths[4]: ("json", evidence),
        }
        delete_candidates = tuple(
            path for path in (
                active_plan_path, canonical_state, legacy_state, active_markdown, active_handoff,
            )
            if file_fingerprint(path) is not None
        )
        publish_transaction(
            root,
            transaction_id,
            writes,
            deletes=delete_candidates,
            metadata=metadata,
        )
    return archive_path


def _path_argument(
    parser: argparse.ArgumentParser,
    flag: str,
    default: str | None,
) -> None:
    parser.add_argument(flag, type=Path, default=Path(default) if default else None)


def command_validate(args: argparse.Namespace) -> None:
    load_plan(args.plan_json)
    print("plan: valid")


def command_render(args: argparse.Namespace) -> None:
    from harness_state import resolve_execution_state

    plan = load_plan(args.plan_json)
    root = _project_root_for_plan(args.plan_json)
    resolution = resolve_execution_state(root, args.state_json)
    state = load_json(resolution.path)
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
                "single-agent": args.single_estimate,
                "mixed": args.mixed_estimate,
                "multi-agent": args.multi_estimate,
            },
        }
        if args.rationale:
            decision["rationale"] = args.rationale
    root = _project_root_for_plan(args.plan_json)
    state_path = args.state_json or root / ".harness/execution-state.json"
    record_mode_decision(args.plan_json, state_path, decision)
    print(f"plan: mode recorded choice={decision['choice']}")


def command_archive(args: argparse.Namespace) -> None:
    from harness_state import resolve_execution_state

    root = args.root.resolve()
    plan = load_plan(args.plan_json)
    resolution = resolve_execution_state(root, args.state_json, allow_pending=True)
    state = load_json(resolution.path)
    try:
        handoff = args.handoff_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"handoff file not found: {args.handoff_file}") from exc
    path = archive_plan(root, plan, state, handoff)
    print(f"plan: archived {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    _path_argument(validate, "--plan-json", ".harness/plan.json")
    validate.set_defaults(handler=command_validate)
    render = commands.add_parser("render")
    _path_argument(render, "--plan-json", ".harness/plan.json")
    _path_argument(render, "--state-json", None)
    _path_argument(render, "--output", "docs/plans/ACTIVE-PLAN.md")
    render.set_defaults(handler=command_render)
    mode = commands.add_parser("mode")
    _path_argument(mode, "--plan-json", ".harness/plan.json")
    _path_argument(mode, "--state-json", None)
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
    _path_argument(archive, "--state-json", None)
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
