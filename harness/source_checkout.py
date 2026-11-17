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


def _git_checked(checkout: Path, error: str, *arguments: str) -> str:
    """Run git and return its stdout; a failure raises `error` with git's stderr."""
    result = _git(checkout, *arguments)
    if result.returncode != 0:
        raise SourceCheckoutError(f"{error}: {result.stderr.strip()}")
    return result.stdout.strip()


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
    top = _git_checked(
        checkout, f"not a git checkout: {checkout}", "rev-parse", "--show-toplevel"
    )
    if Path(top).resolve() != checkout.resolve():
        raise SourceCheckoutError(
            f"{checkout} is not the top of a git checkout (it lies inside {top}); "
            "run self-update from a dedicated harness clone"
        )
    status = _git_checked(
        checkout,
        "cannot read the checkout status",
        "status",
        "--porcelain",
        "--untracked-files=no",
    )
    if status:
        raise SourceCheckoutError(
            f"the harness source checkout {checkout} has uncommitted changes; "
            "commit or discard them, then retry"
        )
    unpushed = _git_checked(
        checkout,
        "cannot compare HEAD with origin",
        "rev-list",
        "--max-count=1",
        "HEAD",
        "--not",
        "--remotes=origin",
    )
    if unpushed:
        raise SourceCheckoutError(
            f"HEAD of {checkout} has commits that are not on origin; push them or move them "
            "to another checkout, then retry"
        )
    branch = ref or _default_ref(checkout)
    if _git(checkout, "check-ref-format", "--branch", branch).returncode != 0:
        raise SourceCheckoutError(f"{branch!r} is not a branch name")
    previous = _git_checked(checkout, "cannot read HEAD", "rev-parse", "HEAD")
    head = (
        _git(checkout, "symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
        or "detached"
    )
    _git_checked(
        checkout,
        f"cannot fetch branch {branch!r} from origin",
        "fetch",
        "--quiet",
        "origin",
        f"refs/heads/{branch}",
    )
    _git_checked(
        checkout,
        f"cannot check out {branch!r}",
        "checkout",
        "--quiet",
        "--detach",
        "FETCH_HEAD",
    )
    current = _git_checked(checkout, "cannot read HEAD", "rev-parse", "HEAD")
    return {
        "ref": branch,
        "previous": previous,
        "previous_head": head,
        "current": current,
    }
