"""Project-scoped learning rules with deterministic promotion."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

from harness_context import discover_identity
from harness_store import atomic_write_json, find_sensitive_patterns, load_json, locked, utc_now


SCHEMA_VERSION = 1
ENTRY_FIELDS = {
    "id", "rule", "scope", "source", "occurrences", "confidence", "status",
    "created_at", "updated_at", "project_identity",
}
APPROVAL_PREFIXES = (
    "please make sure to",
    "make sure to",
    "asegurate de",
    "asegúrate de",
    "por favor",
    "remember to",
    "recuerda",
    "please",
    "always",
    "siempre",
    "must",
    "debes",
    "debe",
)


def memory_path(root: Path) -> Path:
    """Return the single project-memory store for *root*."""
    return Path(root).resolve() / ".harness" / "memory" / "memory.json"


def _project_identity(root: Path) -> str:
    return discover_identity(root)["identity_id"]


def _new_memory(root: Path) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "project_identity": _project_identity(root),
        "entries": [],
    }


def _validate_memory(root: Path, memory: dict) -> None:
    required = {"schema_version", "project_identity", "entries"}
    missing = sorted(required - set(memory))
    if missing:
        raise ValueError(f"memory missing fields: {', '.join(missing)}")
    if memory["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported memory schema: {memory['schema_version']}")
    if memory["project_identity"] != _project_identity(root):
        raise ValueError("memory identity mismatch")
    if not isinstance(memory["entries"], list):
        raise ValueError("memory entries must be an array")
    for entry in memory["entries"]:
        if not isinstance(entry, dict):
            raise ValueError("memory entry must be an object")
        missing = sorted(ENTRY_FIELDS - set(entry))
        if missing:
            raise ValueError(f"memory entry missing fields: {', '.join(missing)}")
        if not isinstance(entry["id"], str) or not entry["id"]:
            raise ValueError("memory entry id must be a non-empty string")
        if not isinstance(entry["rule"], str) or not entry["rule"].strip():
            raise ValueError("memory entry rule must be a non-empty string")
        patterns = find_sensitive_patterns(entry["rule"])
        if patterns:
            raise ValueError(
                f"refusing to load sensitive memory content: {', '.join(patterns)}"
            )
        if entry["scope"] != "project":
            raise ValueError("memory entry scope must be project")
        if not isinstance(entry["source"], str) or not entry["source"]:
            raise ValueError("memory entry source must be a non-empty string")
        if not isinstance(entry["occurrences"], int) or entry["occurrences"] < 1:
            raise ValueError("memory entry occurrences must be a positive integer")
        if entry["confidence"] not in {"candidate", "high"}:
            raise ValueError("memory entry confidence is invalid")
        if entry["status"] not in {"candidate", "active"}:
            raise ValueError("memory entry status is invalid")
        if not all(isinstance(entry[field], str) and entry[field] for field in (
            "created_at", "updated_at", "project_identity",
        )):
            raise ValueError("memory entry timestamps and identity must be non-empty strings")
        if entry["project_identity"] != memory["project_identity"]:
            raise ValueError("memory entry identity mismatch")
        for field in ("supersedes", "notification"):
            if field in entry and (not isinstance(entry[field], str) or not entry[field]):
                raise ValueError(f"memory entry {field} must be a non-empty string")


def load_memory(root: Path) -> dict:
    """Load memory only when it belongs to the current project identity."""
    path = memory_path(root)
    if not path.exists():
        return _new_memory(root)
    memory = load_json(path)
    _validate_memory(root, memory)
    return memory


def _normalized_rule(text: str) -> str:
    text = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in text.casefold()
    )
    text = " ".join(text.split())
    while text:
        for prefix in APPROVAL_PREFIXES:
            if text == prefix:
                return ""
            if text.startswith(f"{prefix} "):
                text = text[len(prefix):].strip()
                break
        else:
            break
    return text


def _rule_hash(text: str) -> str:
    normalized = _normalized_rule(text)
    if not normalized:
        raise ValueError("memory rule must contain content beyond an approval phrase")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _reject_sensitive(text: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("memory rule must be a non-empty string")
    patterns = find_sensitive_patterns(text)
    if patterns:
        raise ValueError(f"refusing to persist sensitive memory content: {', '.join(patterns)}")


def _validate_source(source: str) -> None:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("memory source must be a non-empty string")
    patterns = find_sensitive_patterns(source)
    if patterns:
        raise ValueError(f"refusing to persist sensitive memory source: {', '.join(patterns)}")


def _find_exact(memory: dict, rule_hash: str) -> dict | None:
    for entry in memory["entries"]:
        if _rule_hash(entry["rule"]) == rule_hash:
            return entry
    return None


def _new_entry(root: Path, text: str, source: str, status: str, confidence: str) -> dict:
    rule_hash = _rule_hash(text)
    timestamp = utc_now()
    return {
        "id": f"rule-{rule_hash[:12]}",
        "rule": text,
        "scope": "project",
        "source": source,
        "occurrences": 1,
        "confidence": confidence,
        "status": status,
        "created_at": timestamp,
        "updated_at": timestamp,
        "project_identity": _project_identity(root),
    }


def _save(path: Path, memory: dict) -> None:
    atomic_write_json(path, memory)


def _notification(entry: dict) -> str:
    return f"MEMORY UPDATED: {entry['id']}"


def record_learning(root: Path, text: str, source: str, explicit_always: bool = False) -> dict:
    """Record a project learning, promoting explicit always-rules immediately."""
    _reject_sensitive(text)
    _validate_source(source)
    path = memory_path(root)
    rule_hash = _rule_hash(text)
    with locked(path):
        memory = load_memory(root)
        entry = _find_exact(memory, rule_hash)
        if entry is None:
            entry = _new_entry(
                root,
                text,
                "explicit_always" if explicit_always else source,
                "active" if explicit_always else "candidate",
                "high" if explicit_always else "candidate",
            )
            memory["entries"].append(entry)
        else:
            entry["occurrences"] += 1
            entry["updated_at"] = utc_now()
        if explicit_always:
            entry.update({
                "source": "explicit_always",
                "status": "active",
                "confidence": "high",
                "notification": _notification(entry),
            })
        _save(path, memory)
        return dict(entry)


def promote_repeated_correction(root: Path, text: str) -> dict:
    """Record a correction and activate it after an exact normalized repeat."""
    _reject_sensitive(text)
    path = memory_path(root)
    rule_hash = _rule_hash(text)
    with locked(path):
        memory = load_memory(root)
        entry = _find_exact(memory, rule_hash)
        if entry is None:
            entry = _new_entry(root, text, "correction", "candidate", "candidate")
            memory["entries"].append(entry)
        else:
            entry["occurrences"] += 1
            entry["updated_at"] = utc_now()
            if entry["source"] != "explicit_always":
                entry.update({
                    "source": "repeated_correction",
                    "status": "active",
                    "confidence": "high",
                    "notification": _notification(entry),
                })
        _save(path, memory)
        return dict(entry)


def record_correction(root: Path, text: str) -> dict:
    """Record a correction; non-exact matches stay candidates by design."""
    return promote_repeated_correction(root, text)


def precedence() -> list[str]:
    """Return rule sources from strongest to weakest."""
    return [
        "current explicit user instruction",
        "explicit project rule",
        "learned project memory",
        "AGENTS.md / CLAUDE.md rules",
        "general harness skills",
        "agent defaults",
    ]
