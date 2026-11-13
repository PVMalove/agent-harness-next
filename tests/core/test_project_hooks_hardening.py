"""Hardening of the standalone project hooks: Python 3.9 import safety, fail-closed git calls in
direct_commits.py, pushes that may update every branch, and bounded git in qa-gate-state.py."""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "harness" / "project" / "hooks"
ISSUE_BRANCH = "feature/issue-1-demo"


def _load(filename: str, name: str) -> ModuleType:
    """Import a hook the way the installed copy imports itself (siblings on sys.path)."""
    sys.path.insert(0, str(HOOKS))
    bytecode = sys.dont_write_bytecode
    try:
        spec = importlib.util.spec_from_file_location(name, HOOKS / filename)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        # dataclasses resolve postponed annotations through sys.modules, as for `__main__`.
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = bytecode
        sys.path.remove(str(HOOKS))


@pytest.fixture(scope="module")
def direct_commits() -> ModuleType:
    return _load("direct_commits.py", "direct_commits_hardening")


@pytest.fixture(scope="module")
def qa_gate_state() -> ModuleType:
    return _load("qa-gate-state.py", "qa_gate_state_hardening")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )


def _repo(tmp_path: Path, branch: str) -> Path:
    """A repository with one commit on `branch`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "checkout", "-q", "-b", branch)
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    return repo


@pytest.fixture
def no_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH without any git executable."""
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))


@pytest.mark.parametrize(
    "hook", sorted(path.name for path in HOOKS.glob("*.py")), ids=str
)
def test_every_python_hook_imports_on_python_3_9(hook: str) -> None:
    """The wrappers accept any Python 3.9+: `X | None` in a signature must stay unevaluated."""
    source = (HOOKS / hook).read_text(encoding="utf-8")
    tree = ast.parse(source, feature_version=(3, 9))
    imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
    ]
    assert any(alias.name == "annotations" for node in imports for alias in node.names)


def test_call_is_immutable(direct_commits: ModuleType, tmp_path: Path) -> None:
    found = direct_commits.calls("git -C sub commit -m x", tmp_path)
    assert found is not None and len(found) == 1
    call = found[0]
    assert call.location == (("-C", "sub"),)
    assert call.args == ("-m", "x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        call.cwd = None


def test_a_wrapper_that_changes_directory_leaves_the_call_unresolved(
    direct_commits: ModuleType, tmp_path: Path
) -> None:
    found = direct_commits.calls("env -C /elsewhere git commit -m x", tmp_path)
    assert found is not None and [call.cwd for call in found] == [None]


@pytest.mark.usefixtures("no_git")
def test_a_commit_is_blocked_when_git_cannot_start(
    direct_commits: ModuleType, tmp_path: Path
) -> None:
    reason = direct_commits.block_reason("git commit -m x", tmp_path, tmp_path)
    assert reason == direct_commits.GIT_NO_ANSWER


def test_a_commit_is_blocked_when_git_does_not_answer(
    direct_commits: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def timed_out(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        timeout = kwargs["timeout"]
        assert timeout == direct_commits.GIT_TIMEOUT_SECONDS
        calls.append(timeout)
        raise subprocess.TimeoutExpired(argv, direct_commits.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", timed_out)
    reason = direct_commits.block_reason("git commit -m x", tmp_path, tmp_path)
    assert reason == direct_commits.GIT_NO_ANSWER
    assert calls


@pytest.mark.usefixtures("no_git")
def test_the_grill_docs_exception_needs_an_answer_from_git(
    direct_commits: ModuleType, tmp_path: Path
) -> None:
    command = "git commit -m docs"
    found = direct_commits.calls(command, tmp_path)
    assert found is not None
    assert (
        direct_commits._grill_docs_commit(command, found[0], "integration/new") is False
    )


@pytest.mark.parametrize("path", ["app.py", "CONTEXT.md", "src/app.py"])
def test_grill_docs_exception_blocks_commit_path_arguments(
    tmp_path: Path, path: str
) -> None:
    repo = _repo(tmp_path, "integration/grill")
    remote = tmp_path / "origin.git"
    _git(repo, "init", "--bare", "-q", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    (repo / "CONTEXT.md").write_text("# docs\n", encoding="utf-8")
    _git(repo, "add", "CONTEXT.md")
    payload = {
        "tool_input": {"command": f"git commit -m 'docs: grill' {path}"},
        "cwd": str(repo),
    }
    result = subprocess.run(
        [shutil.which("bash") or "bash", str(HOOKS / "block-direct-master.sh")],
        input=json.dumps(payload),
        text=True,
        encoding="utf-8",
        capture_output=True,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(repo)),
        check=False,
    )
    assert result.returncode == 2, (result.stdout, result.stderr)


@pytest.mark.parametrize("branch", ["master", "integration/grill", ISSUE_BRANCH])
def test_commit_is_blocked_when_git_cannot_resolve_the_branch(
    direct_commits: ModuleType, tmp_path: Path, branch: str
) -> None:
    repo = tmp_path / "unborn"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    # rev-parse exits 128 before the first commit; an empty/HEAD response is not a branch.
    reason = direct_commits.block_reason("git commit -m init app.py", repo, repo)
    assert reason == direct_commits.GIT_NO_ANSWER


@pytest.mark.parametrize(
    "command",
    [
        "git push --all origin",
        "git push origin --branches",
        "git push --mirror origin",
        "git push origin 'refs/heads/*:refs/heads/*'",
        "git push origin '+refs/heads/*'",
    ],
)
def test_a_push_that_may_update_every_branch_is_blocked(
    direct_commits: ModuleType, tmp_path: Path, command: str
) -> None:
    repo = _repo(tmp_path, ISSUE_BRANCH)
    reason = direct_commits.block_reason(command, repo, repo)
    assert reason.startswith("Zero Direct Commits: ")


@pytest.mark.parametrize(
    "command",
    [
        f"git push origin {ISSUE_BRANCH}",
        "git push -u origin HEAD",
        f"git push origin HEAD:{ISSUE_BRANCH}",
        "git commit -m change",
    ],
)
def test_an_issue_branch_still_commits_and_pushes(
    direct_commits: ModuleType, tmp_path: Path, command: str
) -> None:
    repo = _repo(tmp_path, ISSUE_BRANCH)
    assert direct_commits.block_reason(command, repo, repo) == ""


@pytest.mark.parametrize(
    "command", ["git commit -m change", "git push origin HEAD:main"]
)
def test_a_protected_target_is_still_blocked(
    direct_commits: ModuleType, tmp_path: Path, command: str
) -> None:
    repo = _repo(tmp_path, "main")
    assert "запрещён" in direct_commits.block_reason(command, repo, repo)


def test_parsed_is_immutable() -> None:
    pr_commands = _load("pr_commands.py", "pr_commands_hardening")
    parsed = pr_commands.parse("git status; echo $(git log)")
    assert ["git", "status"] in parsed.commands
    with pytest.raises(dataclasses.FrozenInstanceError):
        parsed.opaque = []


def test_qa_gate_git_is_bounded(
    qa_gate_state: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git that does not answer ends the hook with an error (exit 2), never a hang."""

    def timed_out(
        argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["timeout"] == qa_gate_state.GIT_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(argv, qa_gate_state.GIT_TIMEOUT_SECONDS)

    monkeypatch.setattr(subprocess, "run", timed_out)
    with pytest.raises(subprocess.TimeoutExpired):
        qa_gate_state.git(tmp_path, "rev-parse", "HEAD")


def test_literal_heredoc_does_not_taint_an_unrelated_computed_command(
    direct_commits: ModuleType, tmp_path: Path
) -> None:
    command = "$PY -c 'print(1)'\ncat <<'NOTE'\ngit metadata and commit plan\nNOTE\n"
    assert direct_commits.block_reason(command, tmp_path, tmp_path) == ""


@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\ngit commit -m forbidden\nEOF",
        "cat <<EOF\n$(git commit -m forbidden)\nEOF",
        "PLAN=$(cat <<'EOF'\ncommit\nEOF\n)\n$GIT $PLAN",
        "cat <<'EOF' | $SHELL\ngit commit -m forbidden\nEOF",
        "$SHELL <<'EOF'\ngit commit -m forbidden\nEOF",
    ],
)
def test_executable_or_ambiguous_heredoc_git_stays_blocked(
    direct_commits: ModuleType, tmp_path: Path, command: str
) -> None:
    repo = _repo(tmp_path, "master")
    assert direct_commits.block_reason(command, repo, repo)


@pytest.mark.parametrize(
    ("session", "filename", "expected"),
    [
        ("session-716", "notes.md", 0),
        ("different-session", "notes.md", 2),
        ("session-716", "pr-body-716.md", 2),
    ],
)
def test_project_scratchpad_requires_the_current_runtime_session(
    tmp_path: Path,
    session: str,
    filename: str,
    expected: int,
) -> None:
    import json
    import shutil

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("Bash hook")
    path = (
        tmp_path
        / ".harness/.sandboxes/scratch/sessions/session-716/scratchpad"
        / filename
    )
    process = subprocess.run(
        [bash, str(HOOKS / "block-scratch-outside-docs-tasks.sh")],
        input=json.dumps(
            {"session_id": session, "tool_input": {"file_path": str(path)}}
        ),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert process.returncode == expected, process.stderr


def _worktree(tmp_path: Path, repo: Path, branch: str) -> Path:
    """A linked worktree of `repo` on `branch`, under the same temporary root."""
    worker = tmp_path / "worker"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worker))
    return worker


def _exec_payload(
    cwd: Path,
    workdir: object = None,
    command: str = "git add app.py\ngit commit -m change",
) -> dict[str, object]:
    """A second-runtime `exec_command` payload, as the hook receives it."""
    tool_input: dict[str, object] = {"command": command}
    if workdir is not None:
        tool_input["workdir"] = workdir
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "cwd": str(cwd),
        "tool_input": tool_input,
    }


def _direct_master(
    payload: dict[str, object], project: Path
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("the hook is a bash script")
    return subprocess.run(
        [bash, str(HOOKS / "block-direct-master.sh")],
        input=json.dumps(payload),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_exec_command_workdir_selects_the_issue_checkout_over_the_payload_cwd(
    tmp_path: Path,
) -> None:
    main = _repo(tmp_path, "integration/harness-runtime-reliability")
    worker = _worktree(tmp_path, main, ISSUE_BRANCH)

    result = _direct_master(_exec_payload(main, str(worker)), main)

    assert result.returncode == 0, result.stderr
    verdict = json.loads(result.stderr.strip().splitlines()[-1])
    assert (verdict["hook_id"], verdict["decision"]) == ("block-direct-master", "allow")


def test_exec_command_workdir_blocks_a_protected_checkout_despite_an_issue_cwd(
    tmp_path: Path,
) -> None:
    main = _repo(tmp_path, "integration/harness-runtime-reliability")
    worker = _worktree(tmp_path, main, ISSUE_BRANCH)

    result = _direct_master(_exec_payload(worker, str(main)), main)

    assert result.returncode == 2, result.stderr
    assert "integration/harness-runtime-reliability" in result.stderr


def test_a_relative_exec_command_workdir_is_resolved_against_the_payload_cwd(
    tmp_path: Path,
) -> None:
    main = _repo(tmp_path, "integration/harness-runtime-reliability")
    worker = _worktree(tmp_path, main, ISSUE_BRANCH)

    result = _direct_master(_exec_payload(main, os.path.relpath(worker, main)), main)

    assert result.returncode == 0, result.stderr


def test_an_unusable_exec_command_workdir_blocks_a_commit(
    tmp_path: Path,
) -> None:
    main = _repo(tmp_path, "integration/harness-runtime-reliability")
    worker = _worktree(tmp_path, main, ISSUE_BRANCH)
    payload = _exec_payload(worker)
    payload["tool_input"]["workdir"] = 7  # type: ignore[index]

    result = _direct_master(payload, main)

    assert result.returncode == 2, result.stderr
