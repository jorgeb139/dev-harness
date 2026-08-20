#!/usr/bin/env python3
"""Portable execution state machine and recoverable file transactions."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from harness_store import atomic_write_json, atomic_write_text, load_json, locked, utc_now


SCHEMA_VERSION = 2
TRANSACTION_SCHEMA_VERSION = 1
STATUSES = {"pending", "in_progress", "blocked", "completed"}
TRANSITIONS = {
    "pending": {"in_progress"},
    "in_progress": {"blocked", "completed"},
    "blocked": {"in_progress"},
    "completed": set(),
}
GREEN_STATUSES = {"complete", "completed", "green", "passed"}
SAFE_STATE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CANONICAL_STATE_RELATIVE = Path(".harness/execution-state.json")
LEGACY_STATE_RELATIVE = Path("docs/plans/ACTIVE-PLAN.state.json")
ACTIVE_MARKDOWN_RELATIVE = Path("docs/plans/ACTIVE-PLAN.md")
DEFAULT_HANDOFF_RELATIVE = Path("docs/plans/ACTIVE-PLAN.HANDOFF.md")
DEFAULT_PLAN_RELATIVE = Path(".harness/plan.json")


@dataclass(frozen=True)
class ExecutionStateResolution:
    """Resolved read source and synchronized write destinations for execution state."""

    path: Path
    write_paths: tuple[Path, ...]


def now() -> str:
    return utc_now()


def _root_path(root: Path) -> Path:
    return Path(root).resolve()


def _under_root(root: Path, path: Path) -> Path:
    path = Path(path)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _standard_state_paths(root: Path) -> tuple[Path, Path]:
    return root / CANONICAL_STATE_RELATIVE, root / LEGACY_STATE_RELATIVE


def _pending_manifests(root: Path) -> list[Path]:
    transactions = root / ".harness/transactions"
    if not transactions.exists():
        return []
    return sorted(transactions.glob("*/manifest.json"))


def resolve_execution_state(
    root: Path,
    requested: Path | None = None,
    *,
    for_init: bool = False,
    allow_pending: bool = False,
) -> ExecutionStateResolution:
    """Resolve canonical state with deterministic legacy fallback and divergence checks."""
    root = _root_path(root)
    if not allow_pending:
        pending = _pending_manifests(root)
        if pending:
            raise ValueError(f"pending transaction requires recovery: {pending[0]}")
    canonical, legacy = _standard_state_paths(root)
    if requested is not None:
        requested_path = _under_root(root, Path(requested))
        if requested_path not in {canonical, legacy}:
            if requested_path.exists():
                validate_state(load_json(requested_path))
            return ExecutionStateResolution(requested_path, (requested_path,))

    canonical_exists = canonical.exists()
    legacy_exists = legacy.exists()
    if canonical_exists and legacy_exists:
        canonical_value = load_json(canonical)
        legacy_value = load_json(legacy)
        validate_state(canonical_value)
        validate_state(legacy_value)
        if canonical_value != legacy_value:
            raise ValueError("canonical and legacy execution states diverge")
        return ExecutionStateResolution(canonical, (canonical, legacy))
    if canonical_exists:
        validate_state(load_json(canonical))
        return ExecutionStateResolution(canonical, (canonical, legacy))
    if legacy_exists:
        validate_state(load_json(legacy))
        return ExecutionStateResolution(legacy, (canonical, legacy))
    if for_init:
        return ExecutionStateResolution(canonical, (canonical, legacy))
    return ExecutionStateResolution(canonical, (canonical, legacy))


def _candidate_state_paths(root: Path, requested: Path | None) -> tuple[Path, ...]:
    canonical, legacy = _standard_state_paths(root)
    if requested is None:
        return canonical, legacy
    requested_path = _under_root(root, Path(requested))
    if requested_path in {canonical, legacy}:
        return canonical, legacy
    return (requested_path,)


@contextmanager
def locked_paths(paths: list[Path] | tuple[Path, ...]):
    """Acquire shared store locks in deterministic path order."""
    ordered = sorted({Path(path).resolve() for path in paths}, key=str)
    with ExitStack() as stack:
        for path in ordered:
            stack.enter_context(locked(path))
        yield


def file_fingerprint(path: Path) -> str | None:
    path = Path(path)
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    return hashlib.sha256(content).hexdigest()


def value_fingerprint(value: object) -> str:
    content = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _transaction_id(value: str) -> str:
    if not SAFE_STATE_ID.fullmatch(value):
        raise ValueError(f"unsafe transaction ID: {value!r}")
    return value


def transaction_manifest_path(root: Path, transaction_id: str) -> Path:
    root = _root_path(root)
    transaction_id = _transaction_id(transaction_id)
    return root / ".harness/transactions" / transaction_id / "manifest.json"


def _relative_path(root: Path, path: Path) -> str:
    try:
        relative = Path(path).resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"transaction path escapes project root: {path}") from exc
    return relative.as_posix()


def _serialized_content(kind: str, value: object) -> str:
    if kind == "json":
        return json.dumps(value, indent=2, sort_keys=True) + "\n"
    if kind == "text" and isinstance(value, str):
        return value
    raise ValueError(f"unsupported transaction content kind: {kind}")


def _clear_transaction_directory(directory: Path) -> None:
    if not directory.exists():
        return
    for path in sorted(directory.iterdir(), key=lambda item: item.name, reverse=True):
        if path.is_file():
            path.unlink()
        else:
            raise ValueError(f"unexpected transaction directory entry: {path}")
    directory.rmdir()


def _validate_manifest(manifest: dict, transaction_id: str) -> None:
    required = {"schema_version", "transaction_id", "metadata", "writes", "deletes"}
    if not isinstance(manifest, dict) or required - set(manifest):
        raise ValueError("transaction manifest is malformed")
    if manifest["schema_version"] != TRANSACTION_SCHEMA_VERSION:
        raise ValueError(f"unsupported transaction schema: {manifest['schema_version']}")
    if manifest["transaction_id"] != transaction_id:
        raise ValueError("transaction manifest ID mismatch")
    if not isinstance(manifest["metadata"], dict):
        raise ValueError("transaction metadata must be an object")
    if not isinstance(manifest["writes"], list) or not manifest["writes"]:
        raise ValueError("transaction writes must be a non-empty array")
    if not isinstance(manifest["deletes"], list):
        raise ValueError("transaction deletes must be an array")
    for entry in manifest["writes"]:
        if not isinstance(entry, dict) or set(entry) != {
            "destination", "staged", "kind", "before", "desired",
        }:
            raise ValueError("transaction write entry is malformed")
        if entry["kind"] not in {"json", "text"}:
            raise ValueError("transaction write kind is invalid")
        for field in ("destination", "staged", "desired"):
            if not isinstance(entry[field], str) or not entry[field]:
                raise ValueError(f"transaction write {field} is invalid")
        if entry["before"] is not None and not isinstance(entry["before"], str):
            raise ValueError("transaction write before fingerprint is invalid")
    for entry in manifest["deletes"]:
        if not isinstance(entry, dict) or set(entry) != {"destination", "before"}:
            raise ValueError("transaction delete entry is malformed")
        if not isinstance(entry["destination"], str) or not entry["destination"]:
            raise ValueError("transaction delete destination is invalid")
        if not isinstance(entry["before"], str) or not entry["before"]:
            raise ValueError("transaction delete fingerprint is invalid")


def _apply_transaction(root: Path, directory: Path, manifest: dict) -> None:
    for entry in manifest["writes"]:
        destination = root / entry["destination"]
        staged = directory / entry["staged"]
        if file_fingerprint(staged) != entry["desired"]:
            raise ValueError(f"transaction staged payload is corrupt: {staged}")
        current = file_fingerprint(destination)
        if current == entry["desired"]:
            continue
        if current != entry["before"]:
            raise ValueError(f"transaction destination changed: {destination}")
        content = staged.read_text(encoding="utf-8")
        if entry["kind"] == "json":
            atomic_write_json(destination, json.loads(content))
        else:
            atomic_write_text(destination, content)
        if file_fingerprint(destination) != entry["desired"]:
            raise OSError(f"transaction publish verification failed: {destination}")

    for entry in manifest["writes"]:
        destination = root / entry["destination"]
        if file_fingerprint(destination) != entry["desired"]:
            raise OSError(f"transaction write set is incomplete: {destination}")

    for entry in manifest["deletes"]:
        destination = root / entry["destination"]
        current = file_fingerprint(destination)
        if current is None:
            continue
        if current != entry["before"]:
            raise ValueError(f"transaction delete target changed: {destination}")
        destination.unlink()

    _clear_transaction_directory(directory)


def resume_transaction(
    root: Path,
    transaction_id: str,
    expected_metadata: dict | None = None,
) -> bool:
    """Resume a prepared transaction; return False when no transaction exists."""
    root = _root_path(root)
    manifest_path = transaction_manifest_path(root, transaction_id)
    directory = manifest_path.parent
    if not manifest_path.exists():
        if directory.exists():
            _clear_transaction_directory(directory)
        return False
    manifest = load_json(manifest_path)
    _validate_manifest(manifest, transaction_id)
    if expected_metadata is not None and manifest["metadata"] != expected_metadata:
        raise ValueError("pending transaction metadata does not match requested operation")
    _apply_transaction(root, directory, manifest)
    return True


def publish_transaction(
    root: Path,
    transaction_id: str,
    writes: dict[Path, tuple[str, object]],
    *,
    deletes: tuple[Path, ...] = (),
    metadata: dict | None = None,
) -> None:
    """Stage a complete write/delete set and publish it with resumable manifest state."""
    root = _root_path(root)
    transaction_id = _transaction_id(transaction_id)
    if not writes:
        raise ValueError("transaction requires at least one write")
    manifest_path = transaction_manifest_path(root, transaction_id)
    directory = manifest_path.parent
    if manifest_path.exists():
        raise ValueError(f"pending transaction must be resumed first: {manifest_path}")
    if directory.exists():
        _clear_transaction_directory(directory)
    directory.mkdir(parents=True, exist_ok=False)
    write_entries = []
    write_destinations = set()
    try:
        for index, (destination_value, payload) in enumerate(writes.items()):
            destination = Path(destination_value).resolve()
            relative = _relative_path(root, destination)
            if relative in write_destinations:
                raise ValueError(f"duplicate transaction destination: {relative}")
            write_destinations.add(relative)
            kind, value = payload
            content = _serialized_content(kind, value)
            staged_name = f"{index:04d}.payload"
            staged_path = directory / staged_name
            atomic_write_text(staged_path, content)
            write_entries.append({
                "destination": relative,
                "staged": staged_name,
                "kind": kind,
                "before": file_fingerprint(destination),
                "desired": file_fingerprint(staged_path),
            })
        delete_entries = []
        for destination_value in deletes:
            destination = Path(destination_value).resolve()
            relative = _relative_path(root, destination)
            if relative in write_destinations:
                raise ValueError(f"transaction cannot write and delete the same path: {relative}")
            before = file_fingerprint(destination)
            if before is None:
                continue
            delete_entries.append({"destination": relative, "before": before})
        manifest = {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "metadata": metadata or {},
            "writes": write_entries,
            "deletes": delete_entries,
        }
        atomic_write_json(manifest_path, manifest)
    except Exception:
        if not manifest_path.exists():
            _clear_transaction_directory(directory)
        raise
    _apply_transaction(root, directory, manifest)


def load_state(state_path: Path) -> dict:
    state_path = Path(state_path)
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


def _validate_checkpoint_metadata(value: object, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object or null")
    required = {"timestamp", "commit", "test_command", "result"}
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{label} missing fields: {', '.join(missing)}")
    for field in required:
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{label}.{field} must be a non-empty string")


def validate_state(value: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError("state must be a JSON object")
    required = {
        "schema_version", "plan_id", "plan_file", "status", "phase", "task",
        "owner", "branch", "last_verified_commit", "last_completed_task",
        "attempt_count", "attempt_metadata", "selected_mode", "token_estimates",
        "checkpoint_metadata", "next_action", "evidence", "blockers", "updated_at",
        "history",
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
    for field in (
        "plan_id", "plan_file", "task", "owner", "branch", "next_action", "updated_at",
    ):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if not isinstance(value["last_verified_commit"], str):
        raise ValueError("last_verified_commit must be a string")
    if value["last_completed_task"] is not None and (
        not isinstance(value["last_completed_task"], str)
        or not value["last_completed_task"].strip()
    ):
        raise ValueError("last_completed_task must be a non-empty string or null")
    if type(value["attempt_count"]) is not int or value["attempt_count"] < 0:
        raise ValueError("attempt_count must be a non-negative integer")
    if not isinstance(value["attempt_metadata"], list):
        raise ValueError("attempt_metadata must be an array")
    if value["attempt_count"] != len(value["attempt_metadata"]):
        raise ValueError("attempt_count must equal attempt_metadata length")
    for index, attempt in enumerate(value["attempt_metadata"]):
        if not isinstance(attempt, dict):
            raise ValueError(f"attempt_metadata[{index}] must be an object")
        required_attempt = {"attempt", "timestamp", "reason"}
        if required_attempt - set(attempt):
            raise ValueError(f"attempt_metadata[{index}] is missing fields")
        if attempt["attempt"] != index + 1:
            raise ValueError("attempt_metadata attempts must be sequential")
        for field in ("timestamp", "reason"):
            if not isinstance(attempt[field], str) or not attempt[field].strip():
                raise ValueError(f"attempt_metadata[{index}].{field} must be non-empty")
    if value["selected_mode"] is not None and (
        not isinstance(value["selected_mode"], str) or not value["selected_mode"].strip()
    ):
        raise ValueError("selected_mode must be a non-empty string or null")
    if not isinstance(value["token_estimates"], dict):
        raise ValueError("token_estimates must be an object")
    for mode, estimate in value["token_estimates"].items():
        if not isinstance(mode, str) or not mode.strip():
            raise ValueError("token_estimates keys must be non-empty strings")
        if not isinstance(estimate, str) or not estimate.strip():
            raise ValueError(f"token_estimates.{mode} must be a non-empty string")
    if value["selected_mode"] is None and value["token_estimates"]:
        raise ValueError("pre-decision state must use empty token_estimates")
    if value["selected_mode"] is not None and not value["token_estimates"]:
        raise ValueError("selected mode requires token estimates")
    _validate_checkpoint_metadata(value["checkpoint_metadata"], "checkpoint_metadata")
    if not isinstance(value["evidence"], list) or not isinstance(value["blockers"], list):
        raise ValueError("evidence and blockers must be arrays")
    if not all(isinstance(blocker, str) and blocker.strip() for blocker in value["blockers"]):
        raise ValueError("blockers must contain non-empty strings")
    if not isinstance(value["history"], list) or not value["history"]:
        raise ValueError("history must be a non-empty array")
    if value["status"] == "completed":
        if not value["last_verified_commit"]:
            raise ValueError("completed state requires last_verified_commit")
        if value["checkpoint_metadata"] is None:
            raise ValueError("completed state requires checkpoint_metadata")


def _code_span(value: object) -> str:
    text = " ".join(str(value).split())
    runs = [len(match.group(0)) for match in re.finditer(r"`+", text)]
    delimiter = "`" * (max(runs, default=0) + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def _prose(value: object) -> str:
    text = " ".join(str(value).split())
    return re.sub(r"([\\`*_{}\[\]<>#+|])", r"\\\1", text)


def handoff_markdown(value: dict) -> str:
    lines = [
        f"# Handoff: {_prose(value['plan_id'])}", "",
        f"- Status: {_code_span(value['status'])}",
        f"- Phase: {_code_span(value['phase'])}",
        f"- Task: {_code_span(value['task'])}",
        f"- Owner: {_code_span(value['owner'])}",
        f"- Branch: {_code_span(value['branch'])}",
        f"- Last completed task: {_code_span(value['last_completed_task'] or 'none')}",
        f"- Last verified commit: {_code_span(value['last_verified_commit'] or 'none')}",
        f"- Selected mode: {_code_span(value['selected_mode'] or 'pending')}",
        f"- Attempt count: {_code_span(value['attempt_count'])}",
        f"- Updated: {_code_span(value['updated_at'])}", "", "## Next action", "",
        _prose(value["next_action"]), "", "## Blockers", "",
    ]
    lines.extend(f"- {_prose(item)}" for item in value["blockers"] or ["None"])
    lines.extend(["", "## Evidence", ""])
    if value["evidence"]:
        for item in value["evidence"]:
            lines.append(
                f"- {_code_span(item.get('timestamp', 'unknown'))}: "
                f"{_prose(item.get('result', 'no result'))} "
                f"(command: {_code_span(item.get('test_command', 'none'))}, "
                f"commit: {_code_span(item.get('commit', 'none'))})"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Recent history", ""])
    for item in value["history"][-10:]:
        detail = _prose(item.get("detail", ""))
        suffix = f" {detail}" if detail else ""
        lines.append(
            f"- {_code_span(item.get('timestamp', 'unknown'))} "
            f"{_code_span(item['event'])}{suffix}"
        )
    return "\n".join(lines) + "\n"


def save_state(state_path: Path, handoff_path: Path, value: dict) -> None:
    """Compatibility helper for a single explicit state destination."""
    validate_state(value)
    atomic_write_json(state_path, value)
    atomic_write_text(handoff_path, handoff_markdown(value))


def event(value: dict, name: str, detail: str = "") -> None:
    value["updated_at"] = now()
    value["history"].append({"event": name, "detail": detail, "timestamp": value["updated_at"]})


def transition(value: dict, target: str) -> None:
    current = value["status"]
    if target not in TRANSITIONS[current]:
        raise ValueError(f"invalid transition: {current} -> {target}")
    value["status"] = target


def _phase_value(value: object) -> int | str:
    value = str(value)
    if value.isdigit() and value == str(int(value)):
        return int(value)
    return value


def _phase_for_task(plan: dict, task_id: str) -> str:
    for phase in plan["phases"]:
        if any(task["id"] == task_id for task in phase["tasks"]):
            return phase["id"]
    raise ValueError(f"unknown current task ID: {task_id}")


def _evidence_status(evidence: object) -> str | None:
    if isinstance(evidence, dict) and isinstance(evidence.get("status"), str):
        return evidence["status"].casefold()
    return None


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


def _validate_green_checkpoint(checkpoint: object) -> None:
    if not isinstance(checkpoint, dict):
        raise ValueError("implementation checkpoint must be a typed object")
    required = {"status", "commit", "test_command", "result"}
    missing = sorted(required - set(checkpoint))
    if missing:
        raise ValueError(f"implementation checkpoint missing fields: {', '.join(missing)}")
    if _evidence_status(checkpoint) not in GREEN_STATUSES:
        raise ValueError("implementation checkpoint evidence must be green")
    for field in ("commit", "test_command", "result"):
        if not isinstance(checkpoint[field], str) or not checkpoint[field].strip():
            raise ValueError(f"implementation checkpoint {field} must be non-empty")


def validate_task_transition(
    value: dict,
    plan: dict,
    target_phase: str,
    target_task: str,
) -> None:
    """Fail closed unless current and target pointers satisfy every task gate."""
    from harness_plan import task_index, validate_plan

    validate_state(value)
    validate_plan(plan)
    if value["plan_id"] != plan["plan_id"]:
        raise ValueError("state plan_id does not match plan")
    tasks = task_index(plan)
    current_task_id = value["task"]
    if current_task_id not in tasks:
        raise ValueError(f"unknown current task ID: {current_task_id}")
    current_phase = _phase_for_task(plan, current_task_id)
    if str(value["phase"]) != current_phase:
        raise ValueError(
            f"current task {current_task_id} belongs to phase {current_phase}, "
            f"not state phase {value['phase']}"
        )
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
    _validate_green_checkpoint(current["evidence"].get("implementation_checkpoint"))
    required_reviews = ["security", "regression", "tests"]
    for role in current["reviewer_roles"]:
        review_key = _review_key(role)
        if review_key not in required_reviews:
            required_reviews.append(review_key)
    for review in required_reviews:
        if _evidence_status(_review_evidence(current["evidence"], review)) not in GREEN_STATUSES:
            label = "test" if review == "tests" else review
            raise ValueError(f"{label} review evidence must be green")


def _path_from_arg(root: Path, value: str | Path) -> Path:
    return _under_root(root, Path(value))


def _state_transaction_id(root: Path, requested: Path | None) -> str:
    candidates = _candidate_state_paths(root, requested)
    canonical, legacy = _standard_state_paths(root)
    if set(candidates) == {canonical, legacy}:
        return "execution-state"
    digest = hashlib.sha256(str(candidates[0]).encode("utf-8")).hexdigest()[:12]
    return f"execution-state-{digest}"


def _render_projection(plan_path: Path, value: dict) -> str | None:
    candidate = Path(plan_path)
    if not candidate.exists():
        state_plan = Path(value["plan_file"])
        if not state_plan.is_absolute():
            state_plan = Path.cwd() / state_plan
        candidate = state_plan
    if candidate.suffix != ".json" or not candidate.exists():
        return None
    from harness_plan import load_plan, render_markdown

    plan = load_plan(candidate)
    if plan["plan_id"] != value["plan_id"]:
        raise ValueError("state plan_id does not match projection plan")
    return render_markdown(plan, value)


def _persist_state_mutation(
    root: Path,
    resolution: ExecutionStateResolution,
    handoff_path: Path,
    plan_path: Path,
    value: dict,
    transaction_id: str,
) -> None:
    validate_state(value)
    writes: dict[Path, tuple[str, object]] = {}
    for state_path in resolution.write_paths:
        writes[state_path] = ("json", value)
    writes[handoff_path] = ("text", handoff_markdown(value))
    projection = _render_projection(plan_path, value)
    if projection is not None:
        writes[root / ACTIVE_MARKDOWN_RELATIVE] = ("text", projection)
    publish_transaction(
        root,
        transaction_id,
        writes,
        metadata={"operation": "state-mutation", "plan_id": value["plan_id"]},
    )


def _mutation_paths(args: argparse.Namespace) -> tuple[Path, Path, Path | None, tuple[Path, ...], str]:
    root = Path.cwd().resolve()
    requested = Path(args.state_file) if args.state_file else None
    handoff = _path_from_arg(root, args.handoff_file)
    plan = _path_from_arg(root, args.plan_json)
    candidates = _candidate_state_paths(root, requested)
    transaction_id = _state_transaction_id(root, requested)
    return root, handoff, requested, candidates, transaction_id


def mutate(args: argparse.Namespace, operation) -> None:
    root, handoff_path, requested, candidates, transaction_id = _mutation_paths(args)
    lock_targets = list(candidates) + [
        handoff_path,
        _path_from_arg(root, args.plan_json),
        root / ACTIVE_MARKDOWN_RELATIVE,
        transaction_manifest_path(root, transaction_id),
    ]
    with locked_paths(lock_targets):
        resume_transaction(root, transaction_id)
        resolution = resolve_execution_state(root, requested)
        value = load_state(resolution.path)
        operation(value)
        _persist_state_mutation(
            root,
            resolution,
            handoff_path,
            _path_from_arg(root, args.plan_json),
            value,
            transaction_id,
        )
    print(f"state: {value['status']} task={value['task']}")


def command_init(args: argparse.Namespace) -> None:
    root, handoff_path, requested, candidates, transaction_id = _mutation_paths(args)
    lock_targets = list(candidates) + [
        handoff_path,
        _path_from_arg(root, args.plan_json),
        root / ACTIVE_MARKDOWN_RELATIVE,
        transaction_manifest_path(root, transaction_id),
    ]
    with locked_paths(lock_targets):
        resume_transaction(root, transaction_id)
        resolution = resolve_execution_state(root, requested, for_init=True)
        existing = [path for path in resolution.write_paths if path.exists()]
        if existing:
            raise ValueError(f"state already exists: {existing[0]}")
        timestamp = now()
        value = {
            "schema_version": SCHEMA_VERSION,
            "plan_id": args.plan_id,
            "plan_file": args.plan_file,
            "status": "pending",
            "phase": _phase_value(args.phase),
            "task": args.task,
            "owner": args.owner,
            "branch": args.branch,
            "last_verified_commit": "",
            "last_completed_task": None,
            "attempt_count": 0,
            "attempt_metadata": [],
            "selected_mode": None,
            "token_estimates": {},
            "checkpoint_metadata": None,
            "next_action": args.next_action,
            "evidence": [],
            "blockers": [],
            "updated_at": timestamp,
            "history": [],
        }
        event(value, "initialized", f"plan={args.plan_id}")
        _persist_state_mutation(
            root,
            resolution,
            handoff_path,
            _path_from_arg(root, args.plan_json),
            value,
            transaction_id,
        )
    print(f"state: pending task={value['task']}")


def command_start(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        transition(value, "in_progress")
        value["task"] = args.task
        value["next_action"] = args.next_action
        value["blockers"] = []
        event(value, "started", f"task={args.task}")

    mutate(args, operation)


def command_checkpoint(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        if value["status"] != "in_progress":
            raise ValueError("checkpoint requires in_progress state")
        checkpoint = {
            "timestamp": now(),
            "commit": args.commit,
            "test_command": args.test_command,
            "result": args.result,
        }
        value["evidence"].append(dict(checkpoint))
        value["checkpoint_metadata"] = dict(checkpoint)
        value["last_verified_commit"] = args.commit
        value["next_action"] = args.next_action
        event(value, "checkpoint", f"commit={args.commit}")

    mutate(args, operation)


def command_advance(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        if value["status"] != "in_progress":
            raise ValueError("advance requires in_progress state")
        if value["checkpoint_metadata"] is None:
            raise ValueError("advance requires checkpoint evidence")
        from harness_plan import load_plan

        plan = load_plan(_path_from_arg(Path.cwd().resolve(), args.plan_json))
        validate_task_transition(value, plan, str(args.phase), args.task)
        previous_task = value["task"]
        value["last_completed_task"] = previous_task
        value["phase"] = _phase_value(args.phase)
        value["task"] = args.task
        value["next_action"] = args.next_action
        event(value, "advanced", f"from={previous_task} to={args.task}")

    mutate(args, operation)


def command_block(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        transition(value, "blocked")
        value["blockers"].append(args.reason)
        value["attempt_count"] += 1
        value["attempt_metadata"].append({
            "attempt": value["attempt_count"],
            "timestamp": now(),
            "reason": args.reason,
        })
        value["next_action"] = args.next_action
        event(value, "blocked", args.reason)

    mutate(args, operation)


def command_resume(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        transition(value, "in_progress")
        value["blockers"] = []
        value["next_action"] = args.next_action
        event(value, "resumed", args.next_action)

    mutate(args, operation)


def command_complete(args: argparse.Namespace) -> None:
    def operation(value: dict) -> None:
        transition(value, "completed")
        checkpoint = {
            "timestamp": now(),
            "commit": args.commit,
            "test_command": args.test_command,
            "result": args.result,
        }
        value["last_verified_commit"] = args.commit
        value["checkpoint_metadata"] = dict(checkpoint)
        value["next_action"] = "plan complete"
        value["evidence"].append(dict(checkpoint))
        event(value, "completed", f"commit={args.commit}")

    if not args.commit or not args.test_command or not args.result:
        raise ValueError("complete requires --commit, --test-command, and --result")
    mutate(args, operation)


def _read_resolution(args: argparse.Namespace) -> tuple[ExecutionStateResolution, dict]:
    root = Path.cwd().resolve()
    requested = Path(args.state_file) if args.state_file else None
    candidates = _candidate_state_paths(root, requested)
    transaction_id = _state_transaction_id(root, requested)
    with locked_paths(list(candidates) + [transaction_manifest_path(root, transaction_id)]):
        if resume_transaction(root, transaction_id):
            pass
        resolution = resolve_execution_state(root, requested)
        value = load_state(resolution.path)
    return resolution, value


def command_show(args: argparse.Namespace) -> None:
    _, value = _read_resolution(args)
    if args.json:
        print(json.dumps(value, indent=2, sort_keys=True))
    else:
        print(f"{value['plan_id']}: {value['status']} phase={value['phase']} task={value['task']}")
        print(f"next: {value['next_action']}")


def command_validate(args: argparse.Namespace) -> None:
    _, value = _read_resolution(args)
    validate_state(value)
    print("state: valid")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-file")
    parser.add_argument("--handoff-file", default=str(DEFAULT_HANDOFF_RELATIVE))
    parser.add_argument("--plan-json", default=str(DEFAULT_PLAN_RELATIVE))


def build_parser() -> argparse.ArgumentParser:
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


if __name__ == "__main__":
    raise SystemExit(main())
