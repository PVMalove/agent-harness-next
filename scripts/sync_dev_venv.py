#!/usr/bin/env python3
"""Sync .harness/.venv to uv.lock unless it is the main checkout's venv, linked into a worktree.

`make` calls this when pyproject.toml or uv.lock is newer than the venv stamp. A worktree
checkout, a rebase or a merge gives both files a new mtime without changing them. When the
worktree's venv is a link to the main checkout's (`harness worktree-venv`), `uv sync` would
re-sync that shared venv, and under the agent sandbox it cannot even write there (#1188). So a
linked venv is compared by content: the same files need no sync, different files are refused,
because the worktree then needs a venv of its own.

    sync_dev_venv.py <venv> <python>

Standard library only: it runs with the bootstrap Python before the venv exists.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

LOCK_FILES = ("pyproject.toml", "uv.lock")
STAMP_NAME = ".requirements-installed"


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def sync(checkout: Path, venv: Path, python: str) -> int:
    if venv.is_symlink():
        main = venv.resolve().parent.parent
        differing = [
            name for name in LOCK_FILES if _read(checkout / name) != _read(main / name)
        ]
        if not differing:
            print(f"{venv} links to {main}'s venv with the same lock files: no sync")
            return 0
        print(
            f"{venv} links to {main}'s venv, but {', '.join(differing)} differ; a sync would "
            "change the main checkout's venv. Replace the link with a venv of the worktree: "
            f"rm {venv} && UV_PROJECT_ENVIRONMENT={venv} uv sync --locked",
            file=sys.stderr,
        )
        return 1
    result = subprocess.run(["uv", "sync", "--locked", "--python", python], check=False)
    if result.returncode == 0:
        (venv / STAMP_NAME).touch()
    return result.returncode


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(sync(Path.cwd(), Path(sys.argv[1]), sys.argv[2]))
