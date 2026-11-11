"""The project-local console command journal, `.harness/console/commands.jsonl`."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from ...kernel.discovery import discovery_path


def append(repo: Path, record: Mapping[str, object]) -> None:
    """Append one record; the journal directory must be no link and belong to this user."""
    root = discovery_path(repo).parents[3]
    directory = root / "console"
    if directory.is_symlink() or directory.is_junction():
        raise ValueError("console journal directory must not be a link")
    path = directory / "commands.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32" and directory.stat().st_uid != os.getuid():
        raise PermissionError("console journal directory has a foreign owner")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as journal:
        journal.write(json.dumps(record, ensure_ascii=False) + "\n")
