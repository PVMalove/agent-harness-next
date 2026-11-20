"""Non-secret facts about the target project that tailor wizard recommendations."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_MARKERS = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "Makefile")
_QA = {
    "pyproject.toml": "python -m pytest",
    "package.json": "npm test",
    "Cargo.toml": "cargo test",
    "go.mod": "go test ./...",
}


@dataclass(frozen=True)
class ProjectFacts:
    markers: tuple[str, ...]
    default_branch: str | None
    qa_commands: tuple[str, ...]
    platform: str


def _make_targets(makefile: Path) -> set[str]:
    try:
        text = makefile.read_text(encoding="utf-8", errors="replace")[:200_000]
    except OSError:
        return set()
    return {
        line.split(":", 1)[0].strip()
        for line in text.splitlines()
        if ":" in line and not line.startswith(("\t", " ", "#", "."))
    }


def _default_branch(repo: Path) -> str | None:
    try:
        done = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "symbolic-ref",
                "--short",
                "refs/remotes/origin/HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = done.stdout.strip().removeprefix("origin/")
    return name if done.returncode == 0 and name else None


type _Signature = tuple[tuple[str, int | None, int | None], ...]

# The files the facts come from; the remote HEAD names the default branch.
_SOURCES = (*_MARKERS, ".git/refs/remotes/origin/HEAD")


def _signature(repo: Path) -> _Signature:
    """The modification time and size of every source file, or None for a missing one."""
    stamps: list[tuple[str, int | None, int | None]] = []
    for name in _SOURCES:
        try:
            info = (repo / name).stat()
        except OSError:
            stamps.append((name, None, None))
        else:
            stamps.append((name, info.st_mtime_ns, info.st_size))
    return tuple(stamps)


@lru_cache(maxsize=8)
def _facts(root: str, _signature: _Signature) -> ProjectFacts:
    repo = Path(root)
    markers = tuple(name for name in _MARKERS if (repo / name).is_file())
    targets = _make_targets(repo / "Makefile") if "Makefile" in markers else set()
    commands = tuple(
        f"make {name}" for name in ("verify", "test") if name in targets
    ) or tuple(_QA[name] for name in markers if name in _QA)
    return ProjectFacts(
        markers,
        _default_branch(repo),
        commands[:1],
        "windows" if os.name == "nt" else "posix",
    )


def project_facts(repo: Path) -> ProjectFacts:
    """Facts are read again only when a source file changes: the long-lived web server sees a new
    Makefile target or marker without a restart, and an unchanged project costs a few stat calls.
    In a linked worktree `.git` is a file, so a moved remote HEAD is seen after a marker changes."""
    root = repo.expanduser().resolve()
    return _facts(str(root), _signature(root))
