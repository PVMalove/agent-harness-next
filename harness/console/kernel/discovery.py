"""Where the console server of a project is published: the private discovery record path and
its reader. The writer that owns the record lives in `backend/infrastructure/discovery.py`."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import NamedTuple

from harness.storage import storage_path, storage_root


def discovery_path(repo: Path) -> Path:
    """Resolve a known main checkout; never create linked-worktree fallback state."""
    repo = repo.expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode or Path(result.stdout.strip()).resolve() != repo:
        raise ValueError("console discovery requires a Git project root")
    root = storage_root(repo, require_main_checkout=True)
    if not (root.parent / ".git").exists():
        raise ValueError("cannot locate console project owner")
    path = storage_path(repo, "runs", "console") / "server.json"
    if path.parent.parent.parent.parent != root:
        raise ValueError("console storage owner changed during resolution")
    for part in (root, root / ".sandboxes", path.parent.parent, path.parent, path):
        if part.is_symlink() or part.is_junction():
            raise ValueError("console storage must not contain links")
        if sys.platform != "win32" and part.exists() and part.stat().st_uid != os.getuid():
            raise PermissionError("console storage has a foreign owner")
    return path


class ServerEndpoint(NamedTuple):
    """Где слушает Сервер консоли проекта: loopback-порт и токен из discovery-записи."""

    port: int
    token: str


def read_record(repo: Path) -> ServerEndpoint | None:
    """Return the published endpoint, or None when no valid record is readable."""
    try:
        record = json.loads(discovery_path(repo).read_text(encoding="utf-8"))
        port, token = record["port"], record["token"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if isinstance(port, int) and isinstance(token, str):
        return ServerEndpoint(port, token)
    return None
