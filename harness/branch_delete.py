"""Delete the local branch of a merged ticket after checking that nothing is lost (#1196).

The `block-dangerous-git` hook refuses `git branch -D` in every form. This command is the agent's
route instead: it deletes a branch only when the branch matches `branch_pattern`, no worktree has
it checked out, and its tip is preserved, either reachable from a `refs/remotes/origin/*` ref or
the head commit of a merged PR/MR of the project tracker (a squash merge that deleted the remote
branch leaves only the second kind of evidence).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from harness.cleanup import _git, _registered_worktrees

TRACKER_TIMEOUT_SECONDS = 30


class BranchDeleteRefused(ValueError):
    """The branch stays; the message names the unmet condition."""


def delete_merged_branch(repo: Path, branch: str) -> dict[str, str]:
    """Delete `refs/heads/<branch>` when every condition holds; refuse with the first unmet one."""
    checkout = repo.expanduser().resolve()
    pattern = _branch_pattern(checkout)
    if re.fullmatch(pattern, branch) is None:
        raise BranchDeleteRefused(
            f"branch '{branch}' does not match branch_pattern '{pattern}' of .harness/project.json"
        )
    ref = f"refs/heads/{branch}"
    tip = _git(checkout, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if tip.returncode != 0:
        raise BranchDeleteRefused(f"there is no local branch '{branch}'")
    head = tip.stdout.strip()
    registered = _registered_worktrees(checkout)
    if registered is None:
        raise BranchDeleteRefused("git worktree list failed; the checkouts are unknown")
    for path, checked_out in registered.items():
        if checked_out == branch:
            raise BranchDeleteRefused(f"branch '{branch}' is checked out in worktree '{path}'")
    evidence = _on_origin(checkout, head) or _merged_request(checkout, branch, head)
    if evidence is None:
        raise BranchDeleteRefused(
            f"commits of '{branch}' are not preserved: tip {head} is reachable from no "
            "refs/remotes/origin/* ref, and the tracker shows no merged PR/MR with this head "
            "branch and head commit; push the branch or merge its PR/MR first"
        )
    # The old value makes the deletion atomic: a tip that moved after the checks stays.
    deleted = _git(checkout, "update-ref", "-d", ref, head)
    if deleted.returncode != 0:
        raise BranchDeleteRefused(deleted.stderr.strip() or "git update-ref -d failed")
    # The upstream settings of the branch; a write-protected .git/config keeps them, harmlessly.
    _git(checkout, "config", "--remove-section", f"branch.{branch}")
    return {"status": "deleted", "branch": branch, "tip": head, "evidence": evidence}


def _branch_pattern(checkout: Path) -> str:
    project = checkout / ".harness" / "project.json"
    try:
        pattern = json.loads(project.read_text(encoding="utf-8"))["branch_pattern"]
        re.compile(pattern)
    except (OSError, ValueError, KeyError, TypeError, re.error) as exc:
        raise BranchDeleteRefused(
            f"no valid branch_pattern in {project}: {exc}"
        ) from exc
    if not isinstance(pattern, str) or not pattern:
        raise BranchDeleteRefused(f"no valid branch_pattern in {project}")
    return pattern


def _on_origin(checkout: Path, head: str) -> str | None:
    containing = _git(
        checkout,
        "for-each-ref",
        "--contains",
        head,
        "--format=%(refname)",
        "refs/remotes/origin",
    )
    refs = [
        ref
        for ref in containing.stdout.split()
        if containing.returncode == 0 and ref != "refs/remotes/origin/HEAD"
    ]
    return f"reachable from {refs[0]}" if refs else None


def _merged_request(checkout: Path, branch: str, head: str) -> str | None:
    """`merged PR/MR <number>` whose head branch and head commit are the local branch, or None."""
    from harness.health.project_tracker import resolve_project_tracker

    tracker = resolve_project_tracker(checkout).effective
    if tracker.host is None or tracker.project is None:
        return None
    if tracker.type == "github":
        command = [
            "gh", "pr", "list", "--repo", f"{tracker.host}/{tracker.project}",
            "--head", branch, "--state", "merged", "--json", "number,headRefOid",
        ]  # fmt: skip
        number_key, head_key = "number", "headRefOid"
    elif tracker.type == "gitlab":
        command = [
            "glab", "mr", "list", "-R", f"https://{tracker.host}/{tracker.project}",
            "--source-branch", branch, "--merged", "--output", "json",
        ]  # fmt: skip
        number_key, head_key = "iid", "sha"
    else:
        return None
    try:
        result = subprocess.run(
            command,
            cwd=checkout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=dict(os.environ, GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0"),
            timeout=TRACKER_TIMEOUT_SECONDS,
            check=False,
        )
        requests = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    for request in requests if isinstance(requests, list) else []:
        if isinstance(request, dict) and request.get(head_key) == head:
            return f"merged PR/MR {request.get(number_key)} has head commit {head}"
    return None
