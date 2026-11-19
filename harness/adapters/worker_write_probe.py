"""Disposable writes for an external worker's native execution environment."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

SUCCESS = "Harness write probe passed"


def write_targets(
    worktree: Path, report_dir: Path, check_dirs: Iterable[Path], *, writer: bool
) -> list[str]:
    directories = [report_dir, *check_dirs]
    if writer:
        git_dir = subprocess.check_output(
            ["git", "-C", str(worktree), "rev-parse", "--absolute-git-dir"],
            text=True,
        ).strip()
        directories.extend((worktree, Path(git_dir)))
    return list(dict.fromkeys(str(directory) for directory in directories))


def probe_directory(directory: Path) -> None:
    """Prove creation, a byte write and removal without touching existing files."""
    if not directory.is_absolute() or directory.resolve() != directory:
        raise ValueError("expected a canonical directory")
    fd, name = tempfile.mkstemp(prefix=".harness-write-probe-", dir=directory)
    try:
        try:
            os.write(fd, b"1")
        finally:
            os.close(fd)
    finally:
        Path(name).unlink()


def main(argv: list[str]) -> int:
    for path in argv:
        try:
            probe_directory(Path(path))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"write probe refused: {path}: {exc}", file=sys.stderr)
            return 1
    print(SUCCESS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
