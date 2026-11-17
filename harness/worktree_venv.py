"""Give a coordinator issue worktree the main checkout's `.harness/.venv` without a second sync.

A fresh `git worktree add` checkout has no `.harness/.venv`, so brief checks such as `make lint`
cannot run there. Linking is safe only while the worktree locks the same dependencies as the main
checkout: otherwise `make bootstrap` in the worktree would re-sync the main venv through the link.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

VENV_REL = Path(".harness/.venv")
# Files that pin the dev environment; the Makefile re-syncs the venv when either one changes.
LOCK_FILES = ("uv.lock", "pyproject.toml")
SEPARATE_VENV_REMEDY = (
    "create a separate venv in the worktree: "
    "cd {worktree} && UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked"
)


class WorktreeVenvError(ValueError):
    """The worktree venv was not linked; `remedy` names the next step."""

    def __init__(self, message: str, remedy: str) -> None:
        super().__init__(message)
        self.remedy = remedy


def link_worktree_venv(repo: Path, worktree: Path) -> dict[str, object]:
    """Link `<worktree>/.harness/.venv` to the main checkout's venv when both lock the same deps."""
    main = repo.expanduser().resolve()
    target = worktree.expanduser()
    target = (target if target.is_absolute() else main / target).resolve()
    if target not in _registered_worktrees(main) or target == main:
        raise WorktreeVenvError(
            f"worktree '{target}' is not a linked worktree of '{main}'",
            "create it with git worktree add and pass its path",
        )
    source = main / VENV_REL
    if not (source.is_dir() and not source.is_symlink()):
        raise WorktreeVenvError(
            f"main checkout has no venv at '{source}'",
            f"run make bootstrap in {main}",
        )
    link = target / VENV_REL
    if link.is_symlink() and link.resolve() == source.resolve():
        return {"status": "already_linked", "venv": str(link), "target": str(source)}
    if link.exists() or link.is_symlink():
        raise WorktreeVenvError(
            f"'{link}' already exists and is not a link to '{source}'",
            "keep the existing worktree venv; nothing was changed",
        )
    differing = [name for name in LOCK_FILES if _read(main / name) != _read(target / name)]
    if differing:
        raise WorktreeVenvError(
            f"worktree {', '.join(differing)} differs from the main checkout; "
            "linking would let make bootstrap re-sync the main venv",
            SEPARATE_VENV_REMEDY.format(worktree=target),
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(source, link, target_is_directory=True)
    # A fresh checkout makes the identical lock files newer than the venv stamp, and make would
    # re-sync the main venv through the link; give them the main checkout's timestamps instead.
    for name in LOCK_FILES:
        if (main / name).is_file():
            stat = (main / name).stat()
            os.utime(target / name, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    if _git(target, "check-ignore", "-q", VENV_REL.as_posix()).returncode != 0:
        link.unlink()
        raise WorktreeVenvError(
            f"git does not ignore '{VENV_REL.as_posix()}' in the worktree; the link was removed",
            f"add /{VENV_REL.as_posix()} to .gitignore and rerun",
        )
    return {"status": "linked", "venv": str(link), "target": str(source)}


def _registered_worktrees(repo: Path) -> set[Path]:
    """Return the resolved paths that `git worktree list` registers for the repository."""
    result = _git(repo, "worktree", "list", "--porcelain")
    if result.returncode:
        raise WorktreeVenvError(
            result.stderr.strip() or "git worktree list failed",
            "run the command from a Git checkout",
        )
    return {
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    }


def _read(path: Path) -> bytes | None:
    """Return the file bytes, or None when the file is absent."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _git(checkout: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run Git in the checkout without raising on a non-zero exit."""
    argv = ["git", "-c", f"safe.directory={checkout}", "-C", str(checkout), *arguments]
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(argv, 1, "", f"git unavailable: {exc}")
