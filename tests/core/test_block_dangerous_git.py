"""block-dangerous-git finds the git subcommand after any global option (#1196)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[2]
    / "harness"
    / "project"
    / "hooks"
    / "block-dangerous-git.sh"
)
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="the hook is a bash script")


def run_hook(command: str) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


@pytest.mark.parametrize(
    "command",
    [
        # The Evidence table of #1196.
        "git branch -D foo",
        "git -C /tmp/x branch -D foo",
        "git --no-pager branch -D foo",
        "git -c a=b branch -D foo",
        "git -C /tmp/x reset --hard",
        "git -C /tmp/x clean -fd",
        "git -C /tmp/x checkout .",
        "git branch --delete --force foo",
        # The same patterns behind --git-dir, --work-tree and -p.
        "git --git-dir /tmp/x/.git branch -D foo",
        "git --git-dir=/tmp/x/.git reset --hard",
        "git --work-tree /tmp/x clean -f",
        "git --work-tree=/tmp/x restore .",
        "git -p checkout .",
        # Long and reordered synonyms.
        "git clean --force",
        "git clean -df",
        "git branch -d -f foo",
        "git reset HEAD~1 --hard",
        "git checkout -- .",
        "cd /tmp && git -C x branch -D foo",
        "bash -c 'git -C /tmp/x reset --hard'",
    ],
)
def test_blocks_a_destructive_command_behind_any_global_option(command: str) -> None:
    result = run_hook(command)
    assert result.returncode == 2, result.stderr
    assert "Заблокировано" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x branch -d foo",
        "git -C /tmp/x status",
        "git --no-pager log --oneline -3",
        "git -C /tmp/x reset --soft HEAD~1",
        "git -C /tmp/x checkout -- file.py",
        "git -C /tmp/x clean -n",
        "git -C /tmp/x restore --staged .",
        "git -c core.pager=cat branch -f foo HEAD",
        'echo "git -C /tmp/x branch -D foo"',
        "python -c 'import os; os.system(\"git -C x reset --hard\")'",
        "rg -n 'git -C x clean -fd' docs",
    ],
)
def test_passes_a_safe_form(command: str) -> None:
    result = run_hook(command)
    assert result.returncode == 0, result.stderr


def test_branch_delete_refusal_names_the_harness_command() -> None:
    result = run_hook("git -C /tmp/x branch -D feature/issue-1-x")
    assert result.returncode == 2
    assert "harness branch-delete <repo> <branch>" in result.stderr


def test_unparsed_command_falls_back_to_raw_match_after_global_options() -> None:
    result = run_hook("git -C /tmp/x reset --hard 'unclosed")
    assert result.returncode == 2
    assert "git reset --hard" in result.stderr
