"""Deterministic project identity discovery and technical context rendering."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from harness_store import find_sensitive_patterns, fingerprint_files, utc_now


SCHEMA_VERSION = 1
UNKNOWN = "Not detected; user/agent must verify"
MANIFEST_FILES = (
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb",
    "pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "setup.py",
    "Cargo.toml", "go.mod", "Gemfile", "composer.json", "pom.xml", "build.gradle",
    "Makefile",
)
RUNTIME_FILES = (
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".tool-versions",
    ".python-version", ".node-version", ".nvmrc", "tsconfig.json", "vite.config.js",
    "vite.config.ts", "next.config.js", "next.config.ts",
)
SCRIPT_FILES = (
    "health.sh", "build.sh", "test.sh", "scripts/health.sh", "scripts/build.sh",
    "scripts/test.sh",
)
TEST_DIRECTORY_NAMES = {"test", "tests", "spec", "specs", "__tests__", "integration", "e2e"}
IGNORED_DIRECTORIES = {".git", ".harness", "__pycache__", ".venv", "node_modules"}


def _git_output(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _project_root(root: Path) -> Path:
    root = Path(root).resolve()
    top_level = _git_output(root, "rev-parse", "--show-toplevel")
    return Path(top_level).resolve() if top_level else root


def _normalize_remote(remote: str | None) -> str | None:
    if not remote:
        return None
    remote = remote.strip()
    if not remote:
        return None
    if "://" in remote:
        parsed = urlsplit(remote)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        path = parsed.path.rstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return urlunsplit((parsed.scheme, host, path, "", ""))
    remote = remote.rsplit("@", 1)[-1].rstrip("/")
    return remote[:-4] if remote.endswith(".git") else remote


def _identity_id(root: str, name: str, remote: str | None) -> str:
    payload = json.dumps(
        {"name": name, "remote": remote, "root": root},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _manifest_name(root: Path) -> str | None:
    package_json = root / "package.json"
    if not package_json.is_file():
        return None
    try:
        value = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed package.json: {package_json}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"package.json root must be an object: {package_json}")
    name = value.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


def discover_identity(root: Path) -> dict:
    """Return the normalized identity for a project root or one of its subdirectories."""
    project_root = _project_root(root)
    name = _manifest_name(project_root) or project_root.name
    remote = _normalize_remote(_git_output(project_root, "config", "--get", "remote.origin.url"))
    root_text = str(project_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "root": root_text,
        "name": name,
        "remote": remote,
        "identity_id": _identity_id(root_text, name, remote),
    }


def validate_identity(root: Path, stored: dict) -> list[str]:
    """Return identity mismatches, raising ValueError for malformed stored metadata."""
    if not isinstance(stored, dict):
        raise ValueError("project identity must be a JSON object")
    required = {"schema_version", "root", "name", "remote", "identity_id"}
    missing = sorted(required - set(stored))
    if missing:
        raise ValueError(f"project identity missing fields: {', '.join(missing)}")
    if stored["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported identity schema: {stored['schema_version']}")
    if not isinstance(stored["root"], str) or not stored["root"]:
        raise ValueError("project identity root must be a non-empty string")
    if not isinstance(stored["name"], str) or not stored["name"]:
        raise ValueError("project identity name must be a non-empty string")
    if stored["remote"] is not None and not isinstance(stored["remote"], str):
        raise ValueError("project identity remote must be a string or null")
    if not isinstance(stored["identity_id"], str) or not stored["identity_id"]:
        raise ValueError("project identity identity_id must be a non-empty string")

    expected_id = _identity_id(stored["root"], stored["name"], stored["remote"])
    errors = []
    if stored["identity_id"] != expected_id:
        errors.append("stored identity_id does not match stored identity fields")
    current = discover_identity(root)
    for field in ("root", "name", "remote"):
        if stored[field] != current[field]:
            errors.append(f"{field} mismatch: stored={stored[field]!r} current={current[field]!r}")
    return errors


def _top_level_directories(root: Path) -> list[str]:
    return sorted(
        path.name for path in root.iterdir()
        if path.is_dir() and path.name not in IGNORED_DIRECTORIES
    )


def _test_directories(root: Path) -> list[str]:
    return sorted(
        name for name in _top_level_directories(root)
        if name.lower() in TEST_DIRECTORY_NAMES
    )


def _executable_scripts(root: Path) -> list[str]:
    return [path for path in SCRIPT_FILES if (root / path).is_file() and os.access(root / path, os.X_OK)]


def _package_commands(root: Path) -> list[dict[str, str]]:
    package_json = root / "package.json"
    if not package_json.is_file():
        return []
    try:
        value = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed package.json: {package_json}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"package.json root must be an object: {package_json}")
    scripts = value.get("scripts", {})
    if not isinstance(scripts, dict):
        raise ValueError(f"package.json scripts must be an object: {package_json}")
    return [
        {"source": "package.json", "name": name, "command": command}
        for name, command in sorted(scripts.items())
        if isinstance(name, str) and isinstance(command, str)
    ]


def context_fingerprint(root: Path) -> str:
    """Fingerprint relevant tracked facts without reading arbitrary project content."""
    project_root = _project_root(root)
    content = fingerprint_files(project_root, (*MANIFEST_FILES, *RUNTIME_FILES, *SCRIPT_FILES, "README.md", "ARCHITECTURE.md"))
    structure = {
        "content": content,
        "directories": _top_level_directories(project_root),
        "test_directories": _test_directories(project_root),
        "executable_scripts": _executable_scripts(project_root),
    }
    encoded = json.dumps(structure, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_context_inventory(root: Path) -> dict:
    """Inventory local technical facts that can be reproduced from the project tree."""
    project_root = _project_root(root)
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "identity": discover_identity(project_root),
        "fingerprint": context_fingerprint(project_root),
        "generated_at": utc_now(),
        "manifests": [path for path in MANIFEST_FILES if (project_root / path).is_file()],
        "runtime_files": [path for path in RUNTIME_FILES if (project_root / path).is_file()],
        "top_level_directories": _top_level_directories(project_root),
        "test_directories": _test_directories(project_root),
        "executable_scripts": _executable_scripts(project_root),
        "commands": _package_commands(project_root),
        "unknown": {"purpose": UNKNOWN, "deployment": UNKNOWN, "risks": UNKNOWN},
    }
    patterns = find_sensitive_patterns(json.dumps(inventory["commands"], sort_keys=True))
    if patterns:
        raise ValueError(f"refusing to persist sensitive command content: {', '.join(patterns)}")
    return inventory


def _bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items] or ["- None detected"]


def render_context(inventory: dict) -> str:
    """Render a reproducible context document from an inventory returned above."""
    required = {
        "schema_version", "identity", "fingerprint", "generated_at", "manifests",
        "runtime_files", "top_level_directories", "test_directories", "executable_scripts",
        "commands", "unknown",
    }
    if not isinstance(inventory, dict) or required - set(inventory):
        raise ValueError("context inventory is malformed")
    identity = inventory["identity"]
    if not isinstance(identity, dict) or not identity.get("identity_id") or not identity.get("name"):
        raise ValueError("context inventory identity is malformed")
    lines = [
        "# Project Context", "", f"- Schema version: `{inventory['schema_version']}`",
        f"- Project: `{identity['name']}`", f"- Identity ID: `{identity['identity_id']}`",
        f"- Context fingerprint: `{inventory['fingerprint']}`",
        f"- Generated at: `{inventory['generated_at']}`", "", "## Detected Files", "",
        "### Manifests", "",
    ]
    lines.extend(_bullets(inventory["manifests"]))
    lines.extend(["", "### Runtime Files", ""])
    lines.extend(_bullets(inventory["runtime_files"]))
    lines.extend(["", "## Directory Structure", "", "### Top-level Directories", ""])
    lines.extend(_bullets(inventory["top_level_directories"]))
    lines.extend(["", "### Test Directories", ""])
    lines.extend(_bullets(inventory["test_directories"]))
    lines.extend(["", "## Executable Scripts", ""])
    lines.extend(_bullets(inventory["executable_scripts"]))
    lines.extend(["", "## Detected Commands", ""])
    commands = inventory["commands"]
    if commands:
        lines.extend(
            f"- `{command['source']}` `{command['name']}`: `{command['command']}`"
            for command in commands
        )
    else:
        lines.append("- None detected")
    lines.extend([
        "", "## Purpose", "", inventory["unknown"]["purpose"], "", "## Deployment", "",
        inventory["unknown"]["deployment"], "", "## Known Risks", "", inventory["unknown"]["risks"],
        "", "## Refresh", "", "Run `python3 scripts/harness-project.py context check` to inspect freshness.",
        "Run `python3 scripts/harness-project.py context refresh` after intentional project changes.",
        "",
    ])
    rendered = "\n".join(lines)
    patterns = find_sensitive_patterns(rendered)
    if patterns:
        raise ValueError(f"refusing to persist sensitive context: {', '.join(patterns)}")
    return rendered
