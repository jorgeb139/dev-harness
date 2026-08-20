#!/usr/bin/env python3
"""Portable execution state machine and recoverable file transactions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
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
    root = _root_path(root)
    path = Path(path)
    candidate = path if path.is_absolute() else root / path
    lexical = _lexical_absolute(candidate)
    canonical_parent = lexical.parent.resolve() / lexical.name
    return validate_managed_path(root, canonical_parent, "managed")


def _lexical_absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(Path(path))))


def _reject_symlink_components(path: Path, label: str) -> None:
    candidate = _lexical_absolute(path)
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{label} path must not use symlinks: {current}")


def validate_managed_path(root: Path, path: Path, label: str) -> Path:
    """Return a lexical in-project path after rejecting all symlink components."""
    root = _root_path(root)
    candidate = _lexical_absolute(path)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} path escapes project root: {path}") from exc
    _reject_symlink_components(candidate, label)
    return candidate


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
    plan: dict | None = None,
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
                migrate_state(load_json(requested_path), plan=plan)
            return ExecutionStateResolution(requested_path, (requested_path,))

    canonical_exists = canonical.exists()
    legacy_exists = legacy.exists()
    if canonical_exists and legacy_exists:
        canonical_value = migrate_state(load_json(canonical), plan=plan)
        legacy_value = migrate_state(load_json(legacy), plan=plan)
        if canonical_value != legacy_value:
            raise ValueError("canonical and legacy execution states diverge")
        return ExecutionStateResolution(canonical, (canonical, legacy))
    if canonical_exists:
        migrate_state(load_json(canonical), plan=plan)
        return ExecutionStateResolution(canonical, (canonical, legacy))
    if legacy_exists:
        migrate_state(load_json(legacy), plan=plan)
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
    ordered = sorted({_lexical_absolute(path) for path in paths}, key=str)
    for path in ordered:
        _reject_symlink_components(path, "lock target")
        _reject_symlink_components(Path(f"{path}.lock"), "lock file")
    with ExitStack() as stack:
        for path in ordered:
            stack.enter_context(locked(path))
            _reject_symlink_components(path, "lock target")
            _reject_symlink_components(Path(f"{path}.lock"), "lock file")
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


def _stable_internal_directory(root: Path, relative: Path, label: str) -> Path:
    return validate_managed_path(root, root / relative, label)


def _transaction_directory(root: Path, transaction_id: str) -> Path:
    transactions = _stable_internal_directory(
        root, Path(".harness/transactions"), "transaction root"
    )
    return validate_managed_path(
        root, transactions / transaction_id, "transaction directory"
    )


def transaction_manifest_path(root: Path, transaction_id: str) -> Path:
    root = _root_path(root)
    transaction_id = _transaction_id(transaction_id)
    return validate_managed_path(
        root,
        _transaction_directory(root, transaction_id) / "manifest.json",
        "transaction manifest",
    )


def transaction_lock_path(root: Path, transaction_id: str) -> Path:
    """Return a stable lock target outside disposable transaction payload directories."""
    root = _root_path(root)
    transaction_id = _transaction_id(transaction_id)
    locks = _stable_internal_directory(
        root, Path(".harness/transaction-locks"), "transaction lock root"
    )
    return validate_managed_path(root, locks / transaction_id, "transaction lock target")


def _relative_path(root: Path, path: Path) -> str:
    candidate = validate_managed_path(root, path, "transaction destination")
    relative = candidate.relative_to(root)
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
    entries = sorted(directory.iterdir(), key=lambda item: item.name)
    unexpected = [path for path in entries if not path.is_file()]
    if unexpected:
        raise ValueError(f"unexpected transaction directory entry: {unexpected[0]}")
    manifest_path = directory / "manifest.json"
    for path in entries:
        if path != manifest_path:
            path.unlink()
    if manifest_path.exists():
        manifest_path.unlink()


def _resolved_manifest_path(
    base: Path,
    raw_path: object,
    label: str,
    *,
    direct_child: bool = False,
) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"transaction {label} path is invalid")
    relative = Path(raw_path)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"transaction {label} path must be traversal-free and relative")
    base = _lexical_absolute(base)
    _reject_symlink_components(base, f"transaction {label} root")
    resolved = _lexical_absolute(base / relative)
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"transaction {label} path escapes its allowed root") from exc
    _reject_symlink_components(resolved, f"transaction {label}")
    if direct_child and (len(relative.parts) != 1 or resolved.parent != base):
        raise ValueError(f"transaction {label} path must be a direct staged payload")
    return resolved


def _valid_fingerprint(value: object, *, optional: bool) -> bool:
    if optional and value is None:
        return True
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_manifest(
    root: Path,
    directory: Path,
    manifest: dict,
    transaction_id: str,
) -> tuple[list[tuple[dict, Path, Path]], list[tuple[dict, Path]]]:
    required = {"schema_version", "transaction_id", "metadata", "writes", "deletes"}
    allowed = required | {"phase"}
    if (
        not isinstance(manifest, dict)
        or required - set(manifest)
        or set(manifest) - allowed
    ):
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
    if manifest.get("phase", "prepared") not in {"prepared", "applied"}:
        raise ValueError("transaction manifest phase is invalid")
    resolved_writes: list[tuple[dict, Path, Path]] = []
    resolved_deletes: list[tuple[dict, Path]] = []
    destinations: set[Path] = set()
    staged_paths: set[Path] = set()
    for entry in manifest["writes"]:
        if not isinstance(entry, dict) or set(entry) != {
            "destination", "staged", "kind", "before", "desired",
        }:
            raise ValueError("transaction write entry is malformed")
        if entry["kind"] not in {"json", "text"}:
            raise ValueError("transaction write kind is invalid")
        destination = _resolved_manifest_path(root, entry["destination"], "destination")
        staged = _resolved_manifest_path(
            directory, entry["staged"], "staged", direct_child=True
        )
        if destination in destinations:
            raise ValueError("transaction destinations must be unique")
        if staged in staged_paths:
            raise ValueError("transaction staged paths must be unique")
        destinations.add(destination)
        staged_paths.add(staged)
        if not _valid_fingerprint(entry["desired"], optional=False):
            raise ValueError("transaction write desired fingerprint is invalid")
        if not _valid_fingerprint(entry["before"], optional=True):
            raise ValueError("transaction write before fingerprint is invalid")
        resolved_writes.append((entry, destination, staged))
    for entry in manifest["deletes"]:
        if not isinstance(entry, dict) or set(entry) != {"destination", "before"}:
            raise ValueError("transaction delete entry is malformed")
        destination = _resolved_manifest_path(
            root, entry["destination"], "delete destination"
        )
        if destination in destinations:
            raise ValueError("transaction cannot write and delete the same destination")
        destinations.add(destination)
        if not _valid_fingerprint(entry["before"], optional=False):
            raise ValueError("transaction delete fingerprint is invalid")
        resolved_deletes.append((entry, destination))
    return resolved_writes, resolved_deletes


def _apply_transaction(root: Path, directory: Path, manifest: dict) -> None:
    transaction_id = manifest["transaction_id"]
    resolved_writes, resolved_deletes = _validate_manifest(
        root, directory, manifest, transaction_id
    )
    phase = manifest.get("phase", "prepared")
    if phase == "prepared":
        for entry, _, staged in resolved_writes:
            if file_fingerprint(staged) != entry["desired"]:
                raise ValueError(f"transaction staged payload is corrupt: {staged}")
        for entry, destination, staged in resolved_writes:
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

    for entry, destination, _ in resolved_writes:
        if file_fingerprint(destination) != entry["desired"]:
            raise OSError(f"transaction write set is incomplete: {destination}")

    for entry, destination in resolved_deletes:
        current = file_fingerprint(destination)
        if current is None:
            continue
        if current != entry["before"]:
            raise ValueError(f"transaction delete target changed: {destination}")
        destination.unlink()

    if phase != "applied":
        manifest["phase"] = "applied"
        atomic_write_json(directory / "manifest.json", manifest)
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
    _validate_manifest(root, directory, manifest, transaction_id)
    if expected_metadata is not None and manifest["metadata"] != expected_metadata:
        raise ValueError("pending transaction metadata does not match requested operation")
    _apply_transaction(root, directory, manifest)
    return True


def transaction_replay_lock_targets(
    root: Path,
    transaction_id: str,
) -> tuple[tuple[Path, ...], str, dict]:
    """Validate a pending manifest and return its complete lock set and fingerprint."""
    root = _root_path(root)
    manifest_path = transaction_manifest_path(root, transaction_id)
    directory = manifest_path.parent
    manifest = load_json(manifest_path)
    writes, deletes = _validate_manifest(root, directory, manifest, transaction_id)
    fingerprint = file_fingerprint(manifest_path)
    if fingerprint is None:
        raise ValueError("transaction manifest disappeared during recovery")
    destinations = [destination for _, destination, _ in writes]
    destinations.extend(destination for _, destination in deletes)
    destinations.append(transaction_lock_path(root, transaction_id))
    return tuple(destinations), fingerprint, manifest


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
    prepared_writes: list[tuple[Path, str, str, str]] = []
    prepared_deletes: list[tuple[Path, str, str | None]] = []
    destinations: set[str] = set()
    for destination_value, payload in writes.items():
        destination = validate_managed_path(
            root, destination_value, "transaction destination"
        )
        relative = _relative_path(root, destination)
        if relative in destinations:
            raise ValueError(f"duplicate transaction destination: {relative}")
        destinations.add(relative)
        kind, value = payload
        prepared_writes.append(
            (destination, relative, kind, _serialized_content(kind, value))
        )
    for destination_value in deletes:
        destination = validate_managed_path(
            root, destination_value, "transaction delete destination"
        )
        relative = _relative_path(root, destination)
        if relative in destinations:
            raise ValueError(
                f"transaction cannot write and delete the same path: {relative}"
            )
        destinations.add(relative)
        prepared_deletes.append((destination, relative, file_fingerprint(destination)))

    manifest_path = transaction_manifest_path(root, transaction_id)
    directory = manifest_path.parent
    if manifest_path.exists():
        raise ValueError(f"pending transaction must be resumed first: {manifest_path}")
    if directory.exists():
        _clear_transaction_directory(directory)
    directory.mkdir(parents=True, exist_ok=True)
    write_entries = []
    try:
        for index, (destination, relative, kind, content) in enumerate(prepared_writes):
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
        for _, relative, before in prepared_deletes:
            if before is None:
                continue
            delete_entries.append({"destination": relative, "before": before})
        manifest = {
            "schema_version": TRANSACTION_SCHEMA_VERSION,
            "transaction_id": transaction_id,
            "phase": "prepared",
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


def _checkpoint_from_evidence(value: dict) -> dict | None:
    for item in reversed(value.get("evidence", [])):
        if not isinstance(item, dict):
            continue
        required = {"timestamp", "commit", "test_command", "result"}
        if required <= set(item):
            return {field: copy.deepcopy(item[field]) for field in required}
    return None


def _plan_mode_fields(plan: dict) -> tuple[list[str], str, str | None, dict]:
    if not isinstance(plan, dict) or not isinstance(plan.get("mode_options"), dict):
        raise ValueError("canonical plan mode_options are required for state migration")
    mode = plan["mode_options"]
    options = mode.get("options")
    recommendation = mode.get("recommendation")
    choice = mode.get("choice")
    estimates = mode.get("estimates")
    if (
        not isinstance(options, list)
        or not options
        or not all(isinstance(option, str) and option.strip() for option in options)
    ):
        raise ValueError("canonical plan modes are invalid for state migration")
    if len(set(options)) != len(options):
        raise ValueError("canonical plan modes must not contain duplicates")
    if recommendation not in options:
        raise ValueError("canonical plan mode recommendation is invalid")
    if choice is not None and choice not in options:
        raise ValueError("canonical plan mode choice is invalid")
    if not isinstance(estimates, dict) or set(estimates) != set(options):
        raise ValueError("canonical plan mode estimates are incomplete")
    if not all(isinstance(estimates[option], str) and estimates[option].strip() for option in options):
        raise ValueError("canonical plan mode estimates must be non-empty strings")
    return options, recommendation, choice, estimates


def _migrated_mode_decision(value: dict, plan: dict | None) -> dict | None:
    selected = value.get("selected_mode")
    if selected is None:
        return None
    if plan is None:
        raise ValueError(
            "post-decision state migration requires locked canonical plan context"
        )
    _, recommendation, choice, estimates = _plan_mode_fields(plan)
    if selected != choice:
        raise ValueError("state selected mode conflicts with canonical plan mode choice")
    if value.get("token_estimates") != estimates:
        raise ValueError("state token estimates conflict with canonical plan estimates")
    return {
        "recommendation": recommendation,
        "choice": choice,
        "estimates": copy.deepcopy(estimates),
    }


def validate_state_mode_for_plan_contract(plan: dict, state: dict) -> None:
    """Validate the complete canonical mode decision shared by plan/state callers."""
    validate_state(state)
    options, recommendation, choice, estimates = _plan_mode_fields(plan)
    if state["selected_mode"] != choice:
        raise ValueError("state selected_mode does not match plan mode choice")
    expected_estimates = estimates if choice is not None else {}
    if state["token_estimates"] != expected_estimates:
        raise ValueError("state token_estimates do not match the active plan decision")
    if choice is None:
        if state["mode_decision"] is not None:
            raise ValueError("pre-decision state conflicts with the canonical plan")
        return
    decision = state["mode_decision"]
    if decision["recommendation"] != recommendation:
        raise ValueError("state mode recommendation does not match the canonical plan")
    if decision["choice"] != choice:
        raise ValueError("state mode choice does not match the canonical plan")
    if decision["estimates"] != estimates or set(decision["estimates"]) != set(options):
        raise ValueError("state mode estimates do not match every canonical plan mode")


def migrate_state(value: dict, *, plan: dict | None = None) -> dict:
    """Return a validated schema-v2 state, deterministically upgrading schema v1."""
    if not isinstance(value, dict):
        raise ValueError("state must be a JSON object")
    schema_version = value.get("schema_version")
    if schema_version == SCHEMA_VERSION:
        migrated = copy.deepcopy(value)
        if "mode_decision" not in migrated:
            migrated["mode_decision"] = _migrated_mode_decision(migrated, plan)
        validate_state(migrated)
        if plan is not None:
            validate_state_mode_for_plan_contract(plan, migrated)
        return migrated
    if schema_version != 1:
        raise ValueError(f"unsupported state schema: {schema_version}")
    migrated = copy.deepcopy(value)
    migrated["schema_version"] = SCHEMA_VERSION
    migrated.setdefault(
        "last_completed_task",
        migrated.get("task") if migrated.get("status") == "completed" else None,
    )
    migrated.setdefault("attempt_count", 0)
    migrated.setdefault("attempt_metadata", [])
    decision = migrated.get("mode_decision")
    if decision is None:
        decision = _migrated_mode_decision(migrated, plan)
    migrated["mode_decision"] = copy.deepcopy(decision)
    if isinstance(decision, dict):
        migrated.setdefault("selected_mode", decision.get("choice"))
        migrated.setdefault("token_estimates", copy.deepcopy(decision.get("estimates", {})))
    else:
        migrated.setdefault("selected_mode", None)
        migrated.setdefault("token_estimates", {})
    migrated.setdefault("checkpoint_metadata", _checkpoint_from_evidence(migrated))
    validate_state(migrated)
    if plan is not None:
        validate_state_mode_for_plan_contract(plan, migrated)
    return migrated


def load_state(state_path: Path, *, plan: dict | None = None) -> dict:
    state_path = Path(state_path)
    try:
        value = load_json(state_path)
    except ValueError as exc:
        if not state_path.exists():
            raise ValueError(f"state file not found: {state_path}") from exc
        if str(exc).startswith("malformed JSON:"):
            raise ValueError(f"malformed state JSON: {state_path}") from exc
        raise
    return migrate_state(value, plan=plan)


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


def has_substantive_evidence(value: object) -> bool:
    """Return true only when evidence contains a substantive non-status leaf."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(
            key != "status" and has_substantive_evidence(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(has_substantive_evidence(item) for item in value)
    return isinstance(value, (int, float))


def validate_green_review(value: object, label: str) -> None:
    """Require typed green review evidence with a substantive result or evidence field."""
    if not isinstance(value, dict):
        raise ValueError(f"{label} review evidence must be an object")
    status = value.get("status")
    if not isinstance(status, str) or status.casefold() not in GREEN_STATUSES:
        raise ValueError(f"{label} review evidence must be green")
    if not any(
        field in value and has_substantive_evidence(value[field])
        for field in ("result", "evidence")
    ):
        raise ValueError(f"{label} review evidence requires a non-empty result or evidence")


def _validate_mode_state(value: dict) -> None:
    selected = value["selected_mode"]
    estimates = value["token_estimates"]
    decision = value["mode_decision"]
    if selected is None:
        if estimates or decision is not None:
            raise ValueError("pre-decision state requires null mode_decision and empty estimates")
        return
    if not isinstance(decision, dict):
        raise ValueError("selected mode requires a typed mode_decision")
    required = {"recommendation", "choice", "estimates"}
    missing = sorted(required - set(decision))
    if missing:
        raise ValueError(f"mode_decision missing fields: {', '.join(missing)}")
    recommendation = decision["recommendation"]
    choice = decision["choice"]
    decision_estimates = decision["estimates"]
    if not isinstance(recommendation, str) or not recommendation.strip():
        raise ValueError("mode_decision recommendation must be non-empty")
    if not isinstance(choice, str) or not choice.strip():
        raise ValueError("mode_decision choice must be non-empty")
    if not isinstance(decision_estimates, dict) or not decision_estimates:
        raise ValueError("mode_decision estimates must be non-empty")
    if selected != choice:
        raise ValueError("selected_mode must match mode_decision choice")
    if estimates != decision_estimates:
        raise ValueError("token_estimates must match mode_decision estimates")
    if selected not in estimates or recommendation not in estimates:
        raise ValueError("mode decision must use a declared estimated mode")


def validate_state(value: dict) -> None:
    if not isinstance(value, dict):
        raise ValueError("state must be a JSON object")
    required = {
        "schema_version", "plan_id", "plan_file", "status", "phase", "task",
        "owner", "branch", "last_verified_commit", "last_completed_task",
        "attempt_count", "attempt_metadata", "mode_decision", "selected_mode",
        "token_estimates", "checkpoint_metadata", "next_action", "evidence", "blockers",
        "updated_at", "history",
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
    _validate_mode_state(value)
    _validate_checkpoint_metadata(value["checkpoint_metadata"], "checkpoint_metadata")
    if not isinstance(value["evidence"], list) or not isinstance(value["blockers"], list):
        raise ValueError("evidence and blockers must be arrays")
    if not all(isinstance(blocker, str) and blocker.strip() for blocker in value["blockers"]):
        raise ValueError("blockers must contain non-empty strings")
    if not isinstance(value["history"], list) or not value["history"]:
        raise ValueError("history must be a non-empty array")
    for index, item in enumerate(value["history"]):
        if not isinstance(item, dict):
            raise ValueError(f"history[{index}] must be an object")
        missing_history = sorted({"event", "timestamp", "detail"} - set(item))
        if missing_history:
            raise ValueError(
                f"history[{index}] missing fields: {', '.join(missing_history)}"
            )
        for field in ("event", "timestamp"):
            if not isinstance(item[field], str) or not item[field].strip():
                raise ValueError(f"history[{index}].{field} must be a non-empty string")
        if not isinstance(item["detail"], str):
            raise ValueError(f"history[{index}].detail must be a string")
    if value["status"] == "completed":
        if value["last_completed_task"] != value["task"]:
            raise ValueError("completed state requires last_completed_task to equal task")
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
    text = re.sub(r"([\\`*_{}\[\]<>#+|])", r"\\\1", text)
    if re.fullmatch(r"-{3,}", text) or re.match(r"^-\s", text):
        return "\\" + text
    return re.sub(r"^(\d+)([.)])(\s)", r"\1\\\2\3", text)


def handoff_markdown(value: dict) -> str:
    validate_state(value)
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
    from harness_plan import task_index, validate_plan, validate_state_mode_for_plan

    validate_state(value)
    validate_plan(plan)
    if value["plan_id"] != plan["plan_id"]:
        raise ValueError("state plan_id does not match plan")
    validate_state_mode_for_plan(plan, value)
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
        label = "test" if review == "tests" else review
        validate_green_review(_review_evidence(current["evidence"], review), label)


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
    plan_path = _path_from_arg(root, args.plan_json)
    lock_targets = list(candidates) + [
        handoff_path,
        plan_path,
        root / ACTIVE_MARKDOWN_RELATIVE,
        transaction_lock_path(root, transaction_id),
    ]
    with locked_paths(lock_targets):
        resume_transaction(root, transaction_id)
        plan = load_json(plan_path) if plan_path.exists() else None
        resolution = resolve_execution_state(root, requested, plan=plan)
        value = load_state(resolution.path, plan=plan)
        operation(value)
        _persist_state_mutation(
            root,
            resolution,
            handoff_path,
            plan_path,
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
        transaction_lock_path(root, transaction_id),
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
            "mode_decision": None,
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
        value["last_completed_task"] = value["task"]
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
    plan_path = _path_from_arg(root, args.plan_json)
    lock_targets = list(candidates) + [transaction_lock_path(root, transaction_id)]
    if plan_path.exists() or plan_path.is_symlink():
        lock_targets.append(plan_path)
    with locked_paths(lock_targets):
        if resume_transaction(root, transaction_id):
            pass
        plan = load_json(plan_path) if plan_path.exists() else None
        resolution = resolve_execution_state(root, requested, plan=plan)
        value = load_state(resolution.path, plan=plan)
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
