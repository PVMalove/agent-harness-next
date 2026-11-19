# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Prepare and check the coordinator session inherited by in-process workers."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

from harness.json_types import JsonObject
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.core.git_utils import _git
from harness.orchestration.core.utils import CoordinatorError, _repo
from harness.orchestration.core.workspace import (
    _prepare_agent_inbox,
    _probe_writable_directory,
    _require_writable_worktree,
    _validate_branch,
    _validate_worktree,
)
from harness.orchestration.ledger.ledger_ops import _state_root
from harness.storage import sandboxes_root

ARTIFACT_DIRECTORIES = (
    "scratch/inbox",
    "scratch/briefs",
    "runs/qa",
    "runs/tests",
    "logs",
    "cache/npm",
    "cache/ms-playwright",
)
ACCESS_REMEDY = (
    "prepare the directories with 'worktree prepare' from the operator's terminal, "
    "then run 'worktree check' from the coordinator session before retrying"
)


def _session_directories(repo: Path, state: Path) -> list[Path]:
    shared = sandboxes_root(repo)
    directories = [state, *(shared / name for name in ARTIFACT_DIRECTORIES)]
    for directory in directories:
        if directory.resolve() != directory:
            raise CoordinatorError(
                f"the session directory must not use a symlink: {directory}",
                remedy="use a directory at its configured path",
            )
    return directories


def _prepare_directories(directories: list[Path]) -> None:
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CoordinatorError(
                f"cannot prepare the session directory {directory}: {exc.strerror or exc}",
                remedy=ACCESS_REMEDY,
            ) from exc


def require_in_process_artifacts(
    repo: Path, state: Path, *, prepare: bool = False
) -> None:
    """Probe actual writes in the caller's sandbox without touching lifecycle records."""
    directories = _session_directories(repo, state)
    if prepare:
        # An already-running session can still prepare missing roots if its policy allows it.
        _prepare_directories(directories)
    for directory in directories:
        _probe_writable_directory(directory, "session directory", remedy=ACCESS_REMEDY)


def _session_worktree(args: argparse.Namespace, repo: Path) -> Path:
    path = (repo / Path(args.worktree).expanduser()).resolve()
    top_level = Path(_git(repo, "rev-parse", "--show-toplevel")).resolve()
    if (
        repo == path
        or top_level != repo
        or sandboxes_root(repo).parent.parent.resolve() != repo
    ):
        raise CoordinatorError(
            "session setup requires the main checkout and a distinct issue worktree",
            remedy="pass the main checkout as --repo and the issue checkout as --worktree",
        )
    _validate_worktree(repo, str(path))
    git_common_dir = ("rev-parse", "--path-format=absolute", "--git-common-dir")
    if _git(path, *git_common_dir) != _git(repo, *git_common_dir):
        raise CoordinatorError(
            f"the registered issue worktree {path} belongs to a different Git directory",
            remedy="restore the registered worktree before preparing session access",
        )
    _validate_branch(repo, _git(path, "branch", "--show-current"))
    return path


def _codex_command(
    repo: Path, worktree: Path, directories: list[Path], *, network_access: bool
) -> list[str]:
    # The installed coordinator aliases the .harness directory to the harness Python package.
    from harness.adapters.codex_worker import git_commit_permissions

    try:
        git_permissions = git_commit_permissions(worktree)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise CoordinatorError(
            f"cannot resolve Git write permissions for {worktree}: {exc}",
            remedy="check the registered issue branch and Git metadata before preparing the session",
        ) from exc
    filesystem = {
        ":root": "read",
        str(worktree): "write",
        **{
            str(worktree / name): "read"
            for name in (".git", ".agents", ".codex", ".aws")
        },
        **git_permissions,
        **{str(directory): "write" for directory in directories},
    }
    entries = ", ".join(
        f"{json.dumps(path, ensure_ascii=False)} = {json.dumps(mode)}"
        for path, mode in filesystem.items()
    )
    temporary = json.dumps(str(sandboxes_root(repo) / "runs/tests"), ensure_ascii=False)
    return [
        "codex",
        "--cd",
        str(repo),
        "-c",
        'default_permissions="harness-coordinator"',
        "-c",
        "permissions={harness-coordinator={filesystem={"
        + entries
        + "},network={enabled="
        + json.dumps(network_access)
        + "}}}",
        "-c",
        f"shell_environment_policy.set={{TMPDIR={temporary},TMP={temporary},TEMP={temporary}}}",
    ]


def prepare_session(args: argparse.Namespace) -> JsonObject:
    """Prepare the roots and print or run a native session command in the main checkout."""
    repo = _repo(args)
    worktree = _session_worktree(args, repo)
    if getattr(args, "state_dir", None):
        raise CoordinatorError(
            "session launch uses the project's coordinator state directory",
            remedy="omit --state-dir when preparing a new session",
        )
    if args.runtime == "claude" and args.network_access is not None:
        raise CoordinatorError(
            "--network-access applies to Codex sessions",
            remedy="omit --network-access and use the active Claude Code network policy",
        )
    directories = _session_directories(repo, repo / STATE_REL)
    check = shlex.join(
        [
            "python",
            ".harness/orchestration/coordinator.py",
            "--repo",
            ".",
            "worktree",
            "check",
            "--worktree",
            str(worktree),
        ]
    )
    startup_check = (
        f"Run {check} with the shell tool in the session sandbox. "
        "On failure report the denied path and stop before dispatch. "
        "Keep the check inside the sandbox."
    )
    if args.runtime == "codex":
        argv = [
            *_codex_command(
                repo,
                worktree,
                directories,
                network_access=args.network_access == "enabled",
            ),
            "--",
            startup_check,
        ]
    else:
        settings = {
            "sandbox": {
                "filesystem": {"allowWrite": [str(path) for path in directories]}
            }
        }
        argv = [
            "claude",
            "--settings",
            json.dumps(settings),
            "--add-dir",
            str(worktree),
            "--",
            f"Call EnterWorktree with path={json.dumps(str(worktree), ensure_ascii=False)}, "
            "then immediately call "
            f"ExitWorktree with action=keep. Back in the main checkout, {startup_check}",
        ]

    _prepare_directories(directories)
    inbox = sandboxes_root(repo) / "scratch/inbox"
    if (inbox.parent / ".gitignore").is_symlink():
        raise CoordinatorError(
            f"the scratch ignore file must not use a symlink: {inbox.parent / '.gitignore'}",
            remedy="restore the managed scratch ignore file",
        )
    try:
        _prepare_agent_inbox(repo)
        if args.launch:
            return {"exit_code": subprocess.call(argv, cwd=repo)}
    except OSError as exc:
        raise CoordinatorError(
            f"cannot prepare or start the {args.runtime} session: {exc}",
            remedy=ACCESS_REMEDY,
        ) from exc
    return {
        "cwd": str(repo),
        "argv": argv,
        "worktree": str(worktree),
        "check_command": check,
    }


def check_session(args: argparse.Namespace) -> JsonObject:
    """Test the current session after native worktree access has been applied."""
    repo = _repo(args)
    worktree = _session_worktree(args, repo)
    _require_writable_worktree(str(worktree))
    require_in_process_artifacts(repo, _state_root(args, repo))
    return {"worktree": str(worktree), "writable": True}
