"""Shared filesystem and content helpers for dev-harness."""

import datetime as dt
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager, Iterable, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback keeps atomic writes usable.
    fcntl = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def atomic_write_text(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_write_json(path: Path, value: object) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


@contextmanager
def locked(path: Path) -> ContextManager[None]:
    lock_path = Path(f"{path}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield None
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def fingerprint_files(root: Path, relative_paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    root = Path(root)
    for relative_path in relative_paths:
        path = root / relative_path
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            content = b"<missing>"
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


_SENSITIVE_PATTERNS = (
    ("api_key", re.compile(r"(?i)\b(?:api[_-]?key|x-api-key)\b\s*[:=]\s*[^\s,;]+")),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")),
    ("private_key", re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----")),
    ("password", re.compile(r"(?i)\b(?:password|passwd|pwd)\b\s*[:=]\s*[^\s,;]+")),
    ("credential_url", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@[^\s]+")),
)


def find_sensitive_patterns(text: str) -> list[str]:
    return [name for name, pattern in _SENSITIVE_PATTERNS if pattern.search(text)]
