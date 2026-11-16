"""``worktree create`` and ``worktree remove``: the issue worktree through ``harness-runtime`` (#1180).

An agent sandbox mounts the repository's ``.git/worktrees`` read-only, so ``git worktree add`` and
``git worktree remove`` of a sandboxed coordinator stop half done. The runtime works outside the
sandbox: it runs the same git commands for a path under the managed worktree directories. These
commands only ask it; they never fall back to a local git command.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from harness.json_types import JsonObject
from harness.orchestration.core.utils import CoordinatorError, _repo
from harness.orchestration.core.workspace import _require_writable_worktree
from harness.orchestration.runtime_client import RuntimeClient
from harness.storage import sandboxes_root

# The protocol minor that added ``worktree.create`` and ``worktree.remove``. A fixed floor, not
# ``PROTOCOL_VERSION[1]``: a later minor keeps it.
WORKTREE_PROTOCOL_MINOR = 8
# ``git worktree add`` checks out a whole tree and ``git worktree remove`` deletes one.
DEFAULT_TIMEOUT_SECONDS = 120.0


def _absolute(repo: Path, value: str) -> Path:
    """A path of the request, absolute and without symlink resolution: the runtime judges it."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo / path


def _ask(args: argparse.Namespace, operation: str, payload: JsonObject) -> JsonObject:
    reply = RuntimeClient(_repo(args)).call(
        operation,
        operation_id=f"{operation}-{uuid.uuid4().hex}",
        payload=payload,
        timeout_seconds=float(args.timeout),
        requires_minor=WORKTREE_PROTOCOL_MINOR,
    )
    return reply.result


def _session_write_access(worktree: str) -> JsonObject:
    """Whether this session can write the new worktree and its git metadata directory.

    A sandboxed session cannot write a worktree it did not create until it opens that access; the
    coordinator learns so here, not from the writer's failed commit.
    """
    try:
        _require_writable_worktree(worktree)
    except CoordinatorError as exc:
        return {"writable": False, "reason": exc.message, "remedy": exc.remedy}
    return {"writable": True}


def create_worktree(args: argparse.Namespace) -> JsonObject:
    """``worktree create``: a new branch from ``--base`` in a managed worktree directory."""
    repo = _repo(args)
    default = sandboxes_root(repo) / "worktrees" / args.branch.rsplit("/", 1)[-1]
    path = _absolute(repo, args.path) if args.path else default
    result = _ask(
        args,
        "worktree.create",
        {"path": str(path), "branch": args.branch, "base": args.base},
    )
    return {
        **result,
        "session_write_access": _session_write_access(str(result["path"])),
    }


def remove_worktree(args: argparse.Namespace) -> JsonObject:
    """``worktree remove``: remove a clean managed worktree; its branch stays."""
    path = _absolute(_repo(args), args.path)
    return _ask(args, "worktree.remove", {"path": str(path)})
