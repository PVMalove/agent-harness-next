"""The coordinator commands ``worktree create`` and ``worktree remove`` (#1180).

The runtime is replaced at the client: the fake answers a request the way ``harness-runtime``
does, by running the same ``git worktree`` command in the test repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from harness.orchestration import coordinator, worktree_lifecycle
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.runtime_client import RuntimeClientError, RuntimeReply
from tests.orchestration import runtime_store_support as support


def _git(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "--quiet", "--initial-branch=main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "README.md").write_text("project\n", encoding="utf-8")
    (root / ".gitignore").write_text(".harness/\n", encoding="utf-8")
    _git(root, "add", "README.md", ".gitignore")
    _git(root, "commit", "--quiet", "-m", "chore: start")
    return root.resolve()


class FakeRuntime:
    """Answers ``worktree.create`` and ``worktree.remove`` with real git commands."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.calls: list[dict[str, object]] = []

    def call(self, operation: str, **arguments: object) -> RuntimeReply:
        self.calls.append({"operation": operation, **arguments})
        payload = arguments["payload"]
        assert isinstance(payload, dict)
        path = str(payload["path"])
        if operation == "worktree.create":
            branch = str(payload["branch"])
            _git(
                self.repo,
                "worktree",
                "add",
                "--quiet",
                "--no-track",
                "-b",
                branch,
                path,
                str(payload["base"]),
            )
            result = {
                "path": path,
                "branch": branch,
                "head": _git(self.repo, "rev-parse", "HEAD"),
                "created": True,
            }
        else:
            _git(self.repo, "worktree", "remove", path)
            result = {"path": path, "removed": True}
        return RuntimeReply(hello={}, result=result, revision=None)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runtime: object,
    *arguments: str,
) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["coordinator", "worktree", *arguments])
    with mock.patch.object(worktree_lifecycle, "RuntimeClient", return_value=runtime):
        code = coordinator.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_create_asks_the_runtime_for_a_worktree_in_the_managed_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = FakeRuntime(repo)

    code, out, _ = _run(
        monkeypatch,
        capsys,
        runtime,
        "create",
        "--repo",
        str(repo),
        "--branch",
        "feature/issue-7-seven",
        "--base",
        "main",
    )

    expected = repo / ".harness" / ".sandboxes" / "worktrees" / "issue-7-seven"
    assert code == 0
    report = json.loads(out)
    assert report["path"] == str(expected)
    assert report["branch"] == "feature/issue-7-seven"
    assert report["created"] is True
    assert report["session_write_access"] == {"writable": True}
    assert (
        _git(expected, "rev-parse", "--abbrev-ref", "HEAD") == "feature/issue-7-seven"
    )
    call = runtime.calls[0]
    assert call["operation"] == "worktree.create"
    assert call["payload"] == {
        "path": str(expected),
        "branch": "feature/issue-7-seven",
        "base": "main",
    }
    assert call["requires_minor"] == worktree_lifecycle.WORKTREE_PROTOCOL_MINOR


def test_create_resolves_an_explicit_relative_path_against_the_repository(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = FakeRuntime(repo)
    monkeypatch.chdir(repo.parent)

    code, out, _ = _run(
        monkeypatch,
        capsys,
        runtime,
        "create",
        "--repo",
        str(repo),
        "--branch",
        "feature/issue-8-eight",
        "--base",
        "main",
        "--path",
        ".harness/.sandboxes/worktrees/custom",
    )

    assert code == 0
    expected = repo / ".harness" / ".sandboxes" / "worktrees" / "custom"
    assert json.loads(out)["path"] == str(expected)


def test_create_reports_git_metadata_the_session_cannot_write(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = FakeRuntime(repo)
    refusal = CoordinatorError(
        "the session cannot write to the git metadata directory /x: Read-only file system",
        remedy="open write access",
    )
    monkeypatch.setattr(
        worktree_lifecycle, "_require_writable_worktree", mock.Mock(side_effect=refusal)
    )

    code, out, _ = _run(
        monkeypatch,
        capsys,
        runtime,
        "create",
        "--repo",
        str(repo),
        "--branch",
        "feature/issue-9-nine",
        "--base",
        "main",
    )

    assert code == 0
    assert json.loads(out)["session_write_access"] == {
        "writable": False,
        "reason": refusal.message,
        "remedy": "open write access",
    }


def test_remove_asks_the_runtime_and_keeps_the_branch(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = repo / ".harness" / ".sandboxes" / "worktrees" / "issue-10-ten"
    _git(repo, "worktree", "add", "--quiet", "-b", "feature/issue-10-ten", str(tree))
    runtime = FakeRuntime(repo)

    code, out, _ = _run(
        monkeypatch, capsys, runtime, "remove", "--repo", str(repo), "--path", str(tree)
    )

    assert code == 0
    assert json.loads(out) == {"path": str(tree), "removed": True}
    assert not tree.exists()
    assert _git(repo, "branch", "--list", "feature/issue-10-ten") != ""
    assert runtime.calls[0]["operation"] == "worktree.remove"
    assert runtime.calls[0]["payload"] == {"path": str(tree)}


def test_a_refusal_of_the_runtime_exits_2_with_its_code_in_the_remedy(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = mock.Mock()
    runtime.call.side_effect = RuntimeClientError(
        "policy_denied",
        "the path is outside the managed worktree directories",
        remedy="pass a path under .harness/.sandboxes/worktrees",
        domain="policy",
    )

    code, out, err = _run(
        monkeypatch, capsys, runtime, "remove", "--repo", str(repo), "--path", "/etc"
    )

    assert code == 2
    assert out == ""
    lines = err.splitlines()
    assert lines[0] == "ERROR: the path is outside the managed worktree directories"
    assert lines[1].startswith("REMEDY: [policy_denied] ")


def test_the_real_runtime_creates_and_removes_a_managed_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The coordinator CLI as its own process against the built ``harness-runtime`` binary."""
    project = support.coordinator_repository(tmp_path)
    runtime = support.serve_new_project(project)
    try:
        for name, value in runtime.environ.items():
            monkeypatch.setenv(name, value)
        tree = project / ".harness" / ".sandboxes" / "worktrees" / "issue-11-eleven"
        branch = "feature/issue-11-eleven"
        create = ("worktree", "create", "--branch", branch, "--base", "master")

        created = support.coordinator(project, *create)

        assert created.returncode == 0, created.stderr
        report = json.loads(created.stdout)
        assert Path(report["path"]).resolve() == tree.resolve()
        assert report["created"] is True
        assert report["head"] == _git(project, "rev-parse", "master")
        assert report["session_write_access"] == {"writable": True}
        assert _git(tree, "rev-parse", "--abbrev-ref", "HEAD") == branch

        repeated = support.coordinator(project, *create)

        assert repeated.returncode == 0, repeated.stderr
        assert json.loads(repeated.stdout)["created"] is False

        outside = support.coordinator(
            project,
            "worktree",
            "create",
            "--branch",
            "feature/issue-12-twelve",
            "--base",
            "master",
            "--path",
            str(tmp_path / "elsewhere"),
        )

        assert outside.returncode == 2
        assert "[policy_denied]" in outside.stderr
        assert not (tmp_path / "elsewhere").exists()

        removed = support.coordinator(project, "worktree", "remove", "--path", str(tree))

        assert removed.returncode == 0, removed.stderr
        assert json.loads(removed.stdout)["removed"] is True
        assert not tree.exists()
        assert _git(project, "branch", "--list", branch) != ""
    finally:
        runtime.stop()
