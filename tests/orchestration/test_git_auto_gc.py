"""Coordinator git commands never start an auto-gc (#1189).

Under the agent sandbox `.git/worktrees` is read-only; the auto-gc after `git commit` or
`git fetch` expires the reflogs of every worktree and fails there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness.orchestration.core.git_utils import (
    _git,
    git_environment,
    without_auto_gc,
)


def test_appends_gc_auto_after_the_callers_own_entries() -> None:
    env = without_auto_gc(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "safe.directory",
            "GIT_CONFIG_VALUE_0": "*",
        }
    )

    assert env["GIT_CONFIG_COUNT"] == "2"
    assert (env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]) == ("safe.directory", "*")
    assert (env["GIT_CONFIG_KEY_1"], env["GIT_CONFIG_VALUE_1"]) == ("gc.auto", "0")


def test_coordinator_git_sees_gc_auto_zero(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "gc.auto", "1"], check=True
    )

    # The last value wins: the repository's `gc.auto=1` is overridden.
    assert _git(tmp_path, "config", "--get-all", "gc.auto").splitlines()[-1] == "0"
    assert git_environment()["LC_ALL"] == "C"
