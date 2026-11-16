"""Move the harness source checkout to the latest commit of an `origin` branch.

The global `harness` launcher runs `harness/bin/harness.py` of one dedicated checkout, so that
checkout is the source of every project install. `harness self-update` fetches the chosen branch
and detaches HEAD at it; a dirty tree or an unknown branch leaves HEAD where it was.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 120
ORIGIN_HEAD_PREFIX = "refs/remotes/origin/"


class SourceCheckoutError(ValueError):
    """The source checkout was not moved; the message names the reason and the next step."""


def _git(checkout: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceCheckoutError(f"git did not run in {checkout}: {exc}") from exc


def _default_ref(checkout: Path) -> str:
    result = _git(checkout, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    target = result.stdout.strip()
    if result.returncode != 0 or not target.startswith(ORIGIN_HEAD_PREFIX):
        raise SourceCheckoutError(
            "origin/HEAD is not set in the harness source checkout; "
            "pass the branch explicitly: harness self-update --ref <branch>"
        )
    return target.removeprefix(ORIGIN_HEAD_PREFIX)


def update_source_checkout(checkout: Path, ref: str | None) -> dict[str, str]:
    """Fetch `ref` (default: the branch of origin/HEAD) and detach `checkout` at it."""
    status = _git(checkout, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0:
        raise SourceCheckoutError(
            f"not a git checkout: {checkout}: {status.stderr.strip()}"
        )
    if status.stdout.strip():
        raise SourceCheckoutError(
            f"the harness source checkout {checkout} has uncommitted changes; "
            "commit or discard them, then retry"
        )
    branch = ref or _default_ref(checkout)
    previous = _git(checkout, "rev-parse", "HEAD").stdout.strip()
    fetch = _git(checkout, "fetch", "--quiet", "origin", f"refs/heads/{branch}")
    if fetch.returncode != 0:
        raise SourceCheckoutError(
            f"cannot fetch branch {branch!r} from origin: {fetch.stderr.strip()}"
        )
    switch = _git(checkout, "checkout", "--quiet", "--detach", "FETCH_HEAD")
    if switch.returncode != 0:
        raise SourceCheckoutError(
            f"cannot check out {branch!r}: {switch.stderr.strip()}"
        )
    current = _git(checkout, "rev-parse", "HEAD").stdout.strip()
    return {"ref": branch, "previous": previous, "current": current}
