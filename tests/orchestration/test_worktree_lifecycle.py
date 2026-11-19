"""The coordinator commands ``worktree create`` and ``worktree remove`` (#1180).

The runtime is replaced at the client: the fake answers a request the way ``harness-runtime``
does, by running the same ``git worktree`` command in the test repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
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


@pytest.mark.parametrize(
    ("agent", "network_flag"),
    [("codex", ()), ("codex", ("--network-access", "enabled")), ("claude", ())],
)
def test_prepare_provisions_artifacts_and_builds_the_native_session_command(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
    network_flag: tuple[str, ...],
) -> None:
    tree = repo / ".harness/.sandboxes/worktrees/issue-7-seven"
    _git(repo, "worktree", "add", "-q", "-b", "feature/issue-7-seven", str(tree))

    code, out, err = _run(
        monkeypatch,
        capsys,
        None,
        "prepare",
        "--repo",
        str(repo),
        "--worktree",
        str(tree),
        "--runtime",
        agent,
        *network_flag,
    )

    assert code == 0, err
    data = json.loads(out)
    assert data["cwd"] == str(repo)
    argv = data["argv"]
    assert argv[0] == agent
    dirs = [
        repo / ".harness/orchestration/state",
        *(
            repo / ".harness/.sandboxes" / path
            for path in (
                "scratch/inbox",
                "scratch/briefs",
                "runs/qa",
                "runs/tests",
                "logs",
                "cache/npm",
                "cache/ms-playwright",
            )
        ),
    ]
    assert all(path.is_dir() for path in dirs)
    if agent == "claude":
        settings = json.loads(argv[argv.index("--settings") + 1])
        assert settings["sandbox"]["filesystem"]["allowWrite"] == [
            str(path) for path in dirs
        ]
        assert argv[argv.index("--add-dir") + 1] == str(tree)
        assert "EnterWorktree" in argv[-1]
        assert "ExitWorktree" in argv[-1]
        assert "worktree check" in argv[-1]
    else:
        settings = {}
        for i, value in enumerate(argv[:-1]):
            if value == "-c":
                settings.update(tomllib.loads(argv[i + 1]))
        profile = settings["permissions"][settings["default_permissions"]]
        assert profile["network"] == {"enabled": bool(network_flag)}
        filesystem = profile["filesystem"]
        assert filesystem[":root"] == "read"
        assert ":tmpdir" not in filesystem and ":slash_tmp" not in filesystem
        assert settings["shell_environment_policy"]["set"]["TMPDIR"] == str(
            repo / ".harness/.sandboxes/runs/tests"
        )
        gitdir = Path(_git(tree, "rev-parse", "--absolute-git-dir"))
        assert all(filesystem[str(path)] == "write" for path in [*dirs, tree, gitdir])
        assert filesystem[str(repo / ".git/hooks")] == "read"
        # The main checkout is never writable; Git permissions may list it read-only.
        assert filesystem.get(str(repo), "read") == "read"
        assert str(tree.parent) not in filesystem


def test_prepare_launch_starts_in_the_main_checkout_after_provisioning(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = repo / ".harness/.sandboxes/worktrees/issue-7-seven"
    _git(repo, "worktree", "add", "-q", "-b", "feature/issue-7-seven", str(tree))
    started: list[Path] = []

    def launch(argv: list[str], *, cwd: Path) -> int:
        assert argv[0] == "claude"
        assert (cwd / ".harness/.sandboxes/cache/npm").is_dir()
        started.append(cwd)
        return 7

    with mock.patch.object(subprocess, "call", side_effect=launch):
        code, out, _ = _run(
            monkeypatch,
            capsys,
            None,
            "prepare",
            "--repo",
            str(repo),
            "--worktree",
            str(tree),
            "--runtime",
            "claude",
            "--launch",
        )

    assert started == [repo]
    assert code == 7
    assert json.loads(out) == {"exit_code": 7}


def test_worktree_check_detects_a_read_only_artifact_directory(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = repo / ".harness/.sandboxes/worktrees/issue-7-seven"
    _git(repo, "worktree", "add", "-q", "-b", "feature/issue-7-seven", str(tree))
    mkstemp = tempfile.mkstemp
    runs = repo / ".harness/.sandboxes/runs/tests"
    cache = repo / ".harness/.sandboxes/cache/npm"
    denied = {runs, cache}
    arguments = ("--repo", str(repo), "--worktree", str(tree))

    assert (
        _run(monkeypatch, capsys, None, "prepare", *arguments, "--runtime", "claude")[0]
        == 0
    )

    def refuse(*, prefix: str, dir: Path) -> tuple[int, str]:
        if dir in denied:
            raise OSError(30, "Read-only file system")
        return mkstemp(prefix=prefix, dir=dir)

    with mock.patch("tempfile.mkstemp", side_effect=refuse):
        code, _, err = _run(monkeypatch, capsys, None, "check", *arguments)

    assert code == 2
    assert str(runs) in err
    assert "Read-only file system" in err

    # A cache only helps, so an unwritable one is reported and the check passes.
    denied.remove(runs)
    with mock.patch("tempfile.mkstemp", side_effect=refuse):
        code, out, err = _run(monkeypatch, capsys, None, "check", *arguments)

    assert code == 0, err
    assert json.loads(out)["writable"] is True
    assert f"warning: unwritable path not granted: {cache}" in err


@pytest.mark.parametrize("agent", ["codex", "claude"])
def test_prepare_skips_an_optional_symlink_and_refuses_a_required_one(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
) -> None:
    tree = repo / ".harness/.sandboxes/worktrees/issue-7-seven"
    _git(repo, "worktree", "add", "-q", "-b", "feature/issue-7-seven", str(tree))
    shared = repo / ".harness/.sandboxes"
    (shared / "cache").mkdir(parents=True)
    (shared / "runs").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    playwright, qa = shared / "cache/ms-playwright", shared / "runs/qa"
    try:
        playwright.symlink_to(outside, target_is_directory=True)
        qa.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")
    arguments = ("--repo", str(repo), "--worktree", str(tree), "--runtime", agent)

    code, _, err = _run(monkeypatch, capsys, None, "prepare", *arguments)

    assert code == 2
    assert f"required path is a symlink: {qa}" in err

    qa.unlink()
    code, out, err = _run(monkeypatch, capsys, None, "prepare", *arguments)

    assert code == 0, err
    assert f"warning: symlink not granted: {playwright}" in err
    argv = json.loads(out)["argv"]
    assert str(qa) in " ".join(argv)
    assert str(playwright) not in " ".join(argv)
    assert list(outside.iterdir()) == []


def test_prepare_refuses_network_access_for_a_claude_session(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tree = repo / ".harness/.sandboxes/worktrees/issue-7-seven"
    _git(repo, "worktree", "add", "-q", "-b", "feature/issue-7-seven", str(tree))

    code, out, err = _run(
        monkeypatch,
        capsys,
        None,
        "prepare",
        *("--repo", str(repo), "--worktree", str(tree), "--runtime", "claude"),
        *("--network-access", "enabled"),
    )

    assert code == 2
    assert out == ""
    assert "--network-access applies to Codex sessions" in err
    assert not (repo / ".harness/.sandboxes/cache").exists()


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

        removed = support.coordinator(
            project, "worktree", "remove", "--path", str(tree)
        )

        assert removed.returncode == 0, removed.stderr
        assert json.loads(removed.stdout)["removed"] is True
        assert not tree.exists()
        assert _git(project, "branch", "--list", branch) != ""
    finally:
        runtime.stop()
