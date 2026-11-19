"""Disposable writes for an external worker's native execution environment."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

SUCCESS = "Harness write probe passed"
DETAIL_CHARACTERS = 600
_SECRET_KEY = re.compile(r"token|secret|password|credential|api.?key|authorization", re.I)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)([\w-]*(?:api[_-]?key|token|secret|password|authorization)[\w-]*[\"']?\s*[:=]\s*[\"']?)"
    r"([^\s,;\"'}]+)"
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def prepare_directories(directories: Iterable[Path]) -> None:
    """Create the worker's check directories; an existing symlink on the way is refused."""
    for directory in directories:
        if not directory.is_absolute() or directory.resolve() != directory:
            raise ValueError(f"check directory must be canonical, without a symlink: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        if directory.resolve() != directory or not directory.is_dir():
            raise ValueError(f"check directory must be canonical, without a symlink: {directory}")


def safe_detail(text: str) -> str:
    """The tail of a native error with configured secrets and credential assignments masked."""
    for key, value in os.environ.items():
        if len(value) >= 4 and _SECRET_KEY.search(key):
            text = text.replace(value, "<redacted>")
    text = _SECRET_ASSIGNMENT.sub(r"\1<redacted>", text)
    text = " ".join(_CONTROL.sub(" ", text).split())
    return text[-DETAIL_CHARACTERS:]


def write_targets(
    worktree: Path, report_dir: Path, check_dirs: Iterable[Path], *, writer: bool
) -> list[str]:
    directories = [report_dir, *check_dirs]
    if writer:
        git_dir, common = subprocess.check_output(
            [
                "git", "-C", str(worktree), "rev-parse", "--path-format=absolute",
                "--absolute-git-dir", "--git-common-dir",
            ],
            text=True,
        ).splitlines()
        # A linked worktree's own administration is not where a commit lands: objects and
        # refs live in the common directory shared by every checkout.
        shared = Path(common).resolve()
        directories.extend((worktree, Path(git_dir), shared / "objects", shared / "refs"))
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
