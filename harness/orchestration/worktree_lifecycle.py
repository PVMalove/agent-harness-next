"""``worktree create``, ``worktree remove`` and ``worktree commit``: the issue worktree through
``harness-runtime`` (#1180, #1246).

An agent sandbox mounts the repository's ``.git/worktrees`` read-only, so ``git worktree add`` and
``git worktree remove`` of a sandboxed coordinator stop half done. The runtime works outside the
sandbox: it runs the same git commands for a path under the managed worktree directories. These
commands only ask it; they never fall back to a local git command. The same read-only mount stops
``git add``, ``git commit``, ``git rebase`` and ``git merge`` of an in-process writer, so the
runtime runs them for it as well: ``worktree commit``, ``worktree rebase`` and ``worktree merge``.
"""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path

from harness.json_types import JsonObject
from harness.orchestration.core.git_utils import _git
from harness.orchestration.core.utils import CoordinatorError, _repo
from harness.orchestration.core.workspace import (
    WORKTREE_WRITE_REMEDY,
    _probe_writable_directory,
    _require_writable_worktree,
    _validate_branch,
)
from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError
from harness.storage import sandboxes_root

# The protocol minor that added ``worktree.create`` and ``worktree.remove``. A fixed floor, not
# ``PROTOCOL_VERSION[1]``: a later minor keeps it.
WORKTREE_PROTOCOL_MINOR = 8
# The protocol minor that added ``worktree.commit``, ``worktree.rebase`` and ``worktree.merge``
# (#1246).
WORKTREE_COMMIT_PROTOCOL_MINOR = 9
# How long a write-access check waits for the runtime to answer ``status``.
RUNTIME_PROBE_SECONDS = 5.0
# ``git worktree add`` checks out a whole tree and ``git worktree remove`` deletes one.
DEFAULT_TIMEOUT_SECONDS = 120.0


def _absolute(repo: Path, value: str) -> Path:
    """A path of the request, absolute and without symlink resolution: the runtime judges it."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else repo / path


def _ask(
    args: argparse.Namespace,
    operation: str,
    payload: JsonObject,
    requires_minor: int = WORKTREE_PROTOCOL_MINOR,
) -> JsonObject:
    reply = RuntimeClient(_repo(args)).call(
        operation,
        operation_id=f"{operation}-{uuid.uuid4().hex}",
        payload=payload,
        timeout_seconds=float(args.timeout),
        requires_minor=requires_minor,
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


def _issue_worktree(args: argparse.Namespace) -> Path:
    """The worktree of ``--path``, on an issue branch.

    The branch is checked here because the hooks that guard ``git commit``, ``git rebase`` and
    ``git merge`` never see these commands: the worktree must be on an issue branch, never the base
    or an ``integration/*`` one. A stopped rebase detaches HEAD; its branch is the one it rebases.
    """
    repo = _repo(args)
    path = _absolute(repo, args.path)
    branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        for state in ("rebase-merge", "rebase-apply"):
            head_name = Path(
                _git(
                    path,
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-path",
                    f"{state}/head-name",
                )
            )
            if head_name.is_file():
                branch = head_name.read_text(encoding="utf-8").strip()
                branch = branch.removeprefix("refs/heads/")
                break
        else:
            raise CoordinatorError(
                f"the worktree {path} has a detached HEAD",
                remedy="check out the issue branch in the worktree, then repeat the command",
            )
    _validate_branch(repo, branch)
    return path


def commit_worktree(args: argparse.Namespace) -> JsonObject:
    """``worktree commit``: the runtime stages and commits the changes of a managed worktree."""
    path = _issue_worktree(args)
    if args.message_file is not None:
        try:
            message = Path(args.message_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CoordinatorError(
                f"cannot read the commit message file {args.message_file}: {exc}",
                remedy="name a readable UTF-8 file outside the worktree, or pass --message",
            ) from exc
    else:
        message = args.message
    payload: JsonObject = {"path": str(path), "message": message}
    if args.pathspec:
        payload["pathspecs"] = list(args.pathspec)
    return _ask(args, "worktree.commit", payload, WORKTREE_COMMIT_PROTOCOL_MINOR)


def _action(args: argparse.Namespace) -> str:
    """The action of ``worktree rebase`` or ``worktree merge``: a flag, or ``start``."""
    for action in ("continue", "skip", "abort"):
        if getattr(args, action, False):
            return action
    return "start"


def rebase_worktree(args: argparse.Namespace) -> JsonObject:
    """``worktree rebase``: the runtime rebases, continues, skips or aborts in a managed worktree.

    A conflict is an answer, not an error: ``in_progress`` is true and ``conflicts`` lists the
    unmerged paths to resolve before ``--continue``.
    """
    action = _action(args)
    if (action == "start") != (args.upstream is not None):
        raise CoordinatorError(
            "--onto and --upstream go together",
            remedy="pass --onto <target> --upstream <old base>, or one of --continue, --skip, --abort",
        )
    path = _issue_worktree(args)
    payload: JsonObject = {"path": str(path), "action": action}
    if action == "start":
        payload["onto"] = args.onto
        payload["upstream"] = args.upstream
    return _ask(args, "worktree.rebase", payload, WORKTREE_COMMIT_PROTOCOL_MINOR)


def merge_worktree(args: argparse.Namespace) -> JsonObject:
    """``worktree merge``: the runtime merges, continues or aborts in a managed worktree.

    A conflict is an answer, not an error, as in ``worktree rebase``.
    """
    action = _action(args)
    if action != "start" and args.message is not None:
        raise CoordinatorError(
            "--message applies to a new merge",
            remedy="pass --message only with --revision",
        )
    path = _issue_worktree(args)
    payload: JsonObject = {"path": str(path), "action": action}
    if action == "start":
        payload["revision"] = args.revision
        if args.message is not None:
            payload["message"] = args.message
    return _ask(args, "worktree.merge", payload, WORKTREE_COMMIT_PROTOCOL_MINOR)


def runtime_commits(repo: Path) -> bool:
    """Whether the runtime of ``repo`` answers and serves ``worktree.commit``."""
    try:
        client = RuntimeClient(repo)
        # A runtime that never started wrote no token: answer now, not after the retries.
        if not client.paths.token.is_file():
            return False
        reply = client.call(
            "status",
            operation_id=f"status-{uuid.uuid4().hex}",
            timeout_seconds=RUNTIME_PROBE_SECONDS,
            requires_minor=WORKTREE_COMMIT_PROTOCOL_MINOR,
        )
    except RuntimeClientError:
        return False
    features = reply.hello.get("features")
    return isinstance(features, list) and "worktree.commit" in features


def require_committable_worktree(repo: Path, worktree: str) -> str:
    """How a writer commits in ``worktree``: ``git`` when this session can write the worktree
    and its git metadata, ``runtime`` when it can write only the worktree and the runtime serves
    ``worktree.commit``. Anything else is refused with the refusal of the write check.
    """
    try:
        _require_writable_worktree(worktree)
    except CoordinatorError as refusal:
        _probe_writable_directory(
            Path(worktree).resolve(), "issue worktree", remedy=WORKTREE_WRITE_REMEDY
        )
        if runtime_commits(repo):
            return "runtime"
        raise refusal
    return "git"
