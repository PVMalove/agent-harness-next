"""External worker adapters exercised only with dry runs and fake runtimes."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
import tomllib

import pytest

from tests.orchestration import test_claude_adapter as claude_adapter
from tests.orchestration import test_recovery as recovery_tests

ROOT = Path(__file__).resolve().parents[2]
# The installed-example worker of a recovery repository and a reachable model endpoint: the
# fixtures of the claude_code adapter tests.
external_worker = claude_adapter.external_worker
claude_endpoint = claude_adapter.reachable_endpoint

CODEX_ADAPTER = ROOT / "harness/adapters/codex_worker.py"
CODEX_SPEC = importlib.util.spec_from_file_location("codex_worker", CODEX_ADAPTER)
assert CODEX_SPEC and CODEX_SPEC.loader
codex_worker = importlib.util.module_from_spec(CODEX_SPEC)
CODEX_SPEC.loader.exec_module(codex_worker)


@pytest.fixture
def dispatch(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    worker = tmp_path / "worker"
    worker.mkdir()
    subprocess.run(
        ["git", "init", "-b", "feature/issue-715-adapters", str(worker)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(worker),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    sha = subprocess.check_output(
        ["git", "-C", str(worker), "rev-parse", "HEAD"], text=True
    ).strip()
    repo = tmp_path / "main"
    incoming = repo / ".harness/.sandboxes/scratch/inbox"
    incoming.mkdir(parents=True)
    brief: dict[str, object] = {
        "dispatch_id": "dispatch-test",
        "role": "developer",
        "purpose": "work",
        "resolved_transport": "external",
        "resolved_model": "test-model",
        "resolved_effort": "high",
        "allowed_tools": ["Read", "Bash", "Edit"],
        "access": "write",
        "report_staging_path": str(incoming / "dispatch-test.json"),
        "context_package_id": "context-package-test",
        "liveness": {"heartbeat_every_seconds": 300},
        "worktree": str(worker),
        "snapshot_commit": sha,
        "branch": "feature/issue-715-adapters",
    }
    return repo, worker, brief


def invoke(
    dispatch: tuple[Path, Path, dict[str, object]],
    *args: str,
    runtime: str = "claude",
    changes: dict[str, object] | None = None,
) -> subprocess.CompletedProcess[str]:
    repo, worker, brief = dispatch
    payload = dict(brief)
    payload.update(changes or {})
    path = repo / "brief.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / f"harness/adapters/{runtime}_worker.py"),
            "dispatch",
            "--repo",
            str(repo),
            "--brief",
            str(path),
            *args,
        ],
        cwd=worker,
        text=True,
        capture_output=True,
        timeout=15,
    )


def test_claude_dry_run_uses_brief_and_only_incoming_report_directory(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, brief = dispatch
    extra = repo / "retry.txt"
    extra.write_text("Close retry finding finding-1", encoding="utf-8")
    result = invoke(
        dispatch,
        "--dry-run",
        "--claude-bin",
        "/fake/claude",
        "--extra-prompt-file",
        str(extra),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    command = data["command"]
    assert command[0:2] == ["/fake/claude", "-p"]
    assert command[command.index("--model") + 1] == "test-model"
    assert command[command.index("--effort") + 1] == "high"
    assert command[command.index("--allowedTools") + 1] == "Read,Bash,Edit"
    assert command[command.index("--add-dir") + 1] == str(
        Path(str(brief["report_staging_path"])).parent
    )
    assert data["cwd"] == str(worker)
    for text in (
        "dispatch self-report",
        "dispatch heartbeat",
        "report submit",
        "context-package-test",
        "Close retry finding finding-1",
        "ledger_busy",
    ):
        assert text in data["prompt"]


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"role": "qa"}, "role qa"),
        ({"purpose": "publish"}, "purpose publish"),
        ({"resolved_transport": "in-process"}, "external"),
        ({"allowed_tools": None}, "allowed_tools"),
        ({"allowed_tools": []}, "allowed_tools"),
    ],
)
def test_claude_rejects_unsupported_briefs_before_launch(
    dispatch: tuple[Path, Path, dict[str, object]],
    changes: dict[str, object],
    reason: str,
) -> None:
    result = invoke(dispatch, "--dry-run", changes=changes)
    assert result.returncode == 1
    assert reason in result.stderr
    assert not (dispatch[0] / ".harness/.sandboxes/scratch/worker-logs").exists()


def fake_runtime(repo: Path, body: str) -> Path:
    binary = repo / "fake-runtime"
    binary.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    binary.chmod(0o755)
    return binary


CLAUDE_PROBE = """\
import json, os, sys, time
from pathlib import Path
def emit(event):
    print(json.dumps(event), flush=True)
command = json.loads(sys.stdin.readline())['message']['content'].splitlines()[-1]
emit({'type': 'system', 'subtype': 'init'})
emit({'type': 'assistant', 'message': {'content': [
    {'type': 'tool_use', 'id': 'probe', 'name': 'Bash', 'input': {'command': command}},
]}})
emit({'type': 'user', 'message': {'content': [
    {'type': 'tool_result', 'tool_use_id': 'probe', 'content': 'Harness write probe passed'},
]}})
emit({'type': 'result', 'subtype': 'success', 'is_error': False})
prompt = json.loads(sys.stdin.readline())['message']['content']
"""


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_refuses_task_input_without_a_successful_native_bash_result(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    binary = fake_runtime(
        repo,
        CLAUDE_PROBE.replace(
            "'content': 'Harness write probe passed'",
            "'is_error': True, 'content': 'write probe refused: /worker/.git'",
        )
        + f"Path({str(repo / 'unexpected-task')!r}).touch()\n",
    )

    result, _ = run_in_own_group(dispatch, "--claude-bin", str(binary), changes=SUPERVISED)

    assert result.returncode == 1
    assert "write probe refused: /worker/.git" in result.stderr
    assert not (repo / "unexpected-task").exists()


@pytest.mark.parametrize("code", [0, 7])
@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_reports_any_early_exit_with_log_tail(
    dispatch: tuple[Path, Path, dict[str, object]], code: int
) -> None:
    binary = fake_runtime(
        dispatch[0],
        f"import sys\nsys.stdin.readline()\nprint('fake startup failure', file=sys.stderr, flush=True)\nsys.exit({code})\n",
    )
    result = invoke(dispatch, "--claude-bin", str(binary))
    assert result.returncode == 1
    assert f"exited with {code or 1}" in result.stderr
    assert "fake startup failure" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_starts_detached_with_stdin_prompt_in_worker_checkout(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    evidence = repo / "started.json"
    body = CLAUDE_PROBE + f"Path({str(evidence)!r}).write_text(json.dumps(dict(pid=os.getpid(), parent=os.getppid(), session=os.getsid(0), cwd=os.getcwd(), prompt=prompt, args=sys.argv[1:])))\ntime.sleep(30)\n"
    binary = fake_runtime(repo, body)
    try:
        started = time.monotonic()
        result = invoke(dispatch, "--claude-bin", str(binary))
        assert result.returncode == 0, result.stderr
        assert time.monotonic() - started < 10
        data = json.loads(evidence.read_text())
        assert data["parent"] == data["session"]
        assert data["cwd"] == str(worker)
        assert "dispatch self-report" in data["prompt"]
        assert "--model" in data["args"]
    finally:
        if evidence.exists():
            os.kill(json.loads(evidence.read_text())["pid"], 15)


SUPERVISED: dict[str, object] = {"execution": {"kind": "process"}}


def run_in_own_group(
    dispatch: tuple[Path, Path, dict[str, object]],
    *args: str,
    runtime: str = "claude",
    changes: dict[str, object] | None = None,
) -> tuple[subprocess.CompletedProcess[str], int]:
    """Run the adapter as a group leader, as the runtime does; return its result and pid."""
    repo, worker, brief = dispatch
    payload = dict(brief)
    payload.update(changes or {})
    path = repo / "brief.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / f"harness/adapters/{runtime}_worker.py"),
            "dispatch",
            "--repo",
            str(repo),
            "--brief",
            str(path),
            *args,
        ],
        cwd=worker,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    stdout, stderr = process.communicate(timeout=30)
    return (
        subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr),
        process.pid,
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_supervised_runs_the_worker_in_the_foreground_and_returns_its_code(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    evidence = repo / "started.json"
    body = (
        CLAUDE_PROBE
        +
        f"Path({str(evidence)!r}).write_text(json.dumps(dict(pgid=os.getpgid(0), "
        "cwd=os.getcwd(), prompt=prompt, args=sys.argv[1:])))\n"
        'print(\'{"type":"system"}\', flush=True)\n'
        "sys.exit(7)\n"
    )
    binary = fake_runtime(repo, body)
    result, adapter_pid = run_in_own_group(
        dispatch, "--claude-bin", str(binary), changes=SUPERVISED
    )
    assert result.returncode == 7, result.stderr
    assert '{"type":"system"}' in result.stdout
    data = json.loads(evidence.read_text())
    assert data["pgid"] == adapter_pid
    assert data["cwd"] == str(worker)
    assert "dispatch self-report" in data["prompt"]
    args = data["args"]
    assert args[0] == "-p"
    assert args[args.index("--input-format") + 1] == "stream-json"
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in args
    assert not (repo / ".harness/.sandboxes/scratch/worker-logs").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
def test_claude_supervised_reports_a_signalled_worker_as_128_plus_signal(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    binary = fake_runtime(
        dispatch[0], "import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n"
    )
    result, _ = run_in_own_group(
        dispatch, "--claude-bin", str(binary), changes=SUPERVISED
    )
    assert result.returncode == 128 + signal.SIGTERM


def test_claude_supervised_streams_a_prompt_over_the_argument_bound(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    extra = dispatch[0] / "retry.txt"
    extra.write_text("x" * 130000, encoding="utf-8")
    result = invoke(
        dispatch,
        "--dry-run",
        "--claude-bin",
        "/fake/claude",
        "--extra-prompt-file",
        str(extra),
        changes=SUPERVISED,
    )
    assert result.returncode == 0
    plan = json.loads(result.stdout)
    assert len(plan["prompt"]) > 130000
    assert plan["prompt"] not in plan["command"]


def test_claude_supervised_dry_run_shows_probe_and_prompt_separately(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    result = invoke(
        dispatch, "--dry-run", "--claude-bin", "/fake/claude", changes=SUPERVISED
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    command = data["command"]
    assert command[0:2] == ["/fake/claude", "-p"]
    assert "worker_write_probe.py" in data["probe"]
    assert data["prompt"] not in command
    assert command[command.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in command


def test_claude_dispatch_help_lists_entrypoint_arguments(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    result = invoke(dispatch, "--help")
    assert result.returncode == 0
    assert "--repo" in result.stdout and "--brief" in result.stdout
    assert "--extra-prompt-file" in result.stdout and "--claude-bin" in result.stdout


@pytest.mark.parametrize("access", ["write", "read-only"])
def test_codex_dry_run_uses_brief_sandbox_and_retry_prompt(
    dispatch: tuple[Path, Path, dict[str, object]], access: str
) -> None:
    repo, worker, brief = dispatch
    extra = repo / "retry.txt"
    extra.write_text("Close codex retry finding", encoding="utf-8")
    result = invoke(
        dispatch,
        "--dry-run",
        "--codex-bin",
        "/fake/codex",
        "--extra-prompt-file",
        str(extra),
        runtime="codex",
        changes={"access": access},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    command = data["command"]
    assert command[:2] == ["/fake/codex", "app-server"]
    assert data["thread_start"]["model"] == "test-model"
    assert data["thread_start"]["config"] == {"model_reasoning_effort": "high"}
    assert data["thread_start"]["permissions"] == "harness-worker"
    assert data["thread_start"]["approvalPolicy"] == "never"
    assert data["thread_start"]["cwd"] == str(worker)
    assert "--sandbox" not in command
    assert "danger-full-access" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    for text in (
        "dispatch self-report",
        "dispatch heartbeat",
        "report submit",
        "context-package-test",
        "Close codex retry finding",
        "Allowed tools: Read, Bash, Edit",
    ):
        assert text in data["prompt"]


def test_codex_read_only_worker_can_write_lifecycle_evidence_without_source_writes(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, brief = dispatch

    result = invoke(
        dispatch, "--dry-run", runtime="codex", changes={"access": "read-only"}
    )

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    command = data["command"]
    assert "--sandbox" not in command, "legacy read-only disables lifecycle writes"
    overrides = [
        command[index + 1] for index, value in enumerate(command) if value == "--config"
    ]
    config: dict[str, object] = {}
    for override in overrides:
        parsed = tomllib.loads(override)
        config.update(parsed)
    profile_name = config["default_permissions"]
    assert isinstance(profile_name, str)
    permissions = config["permissions"]
    assert isinstance(permissions, dict)
    profile = permissions[profile_name]
    filesystem = profile["filesystem"]
    assert profile["network"] == {"enabled": False}
    assert filesystem[str(worker)] == "read"
    assert filesystem[str(repo / ".harness/orchestration/state")] == "write"
    assert filesystem[str(Path(str(brief["report_staging_path"])).parent)] == "write"
    assert filesystem[":root"] == "read"


def test_codex_writer_keeps_runtime_metadata_read_only(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    _, worker, _ = dispatch

    result = invoke(dispatch, "--dry-run", runtime="codex")

    assert result.returncode == 0, result.stderr
    command = json.loads(result.stdout)["command"]
    configs = [
        tomllib.loads(command[i + 1])
        for i, value in enumerate(command)
        if value == "--config"
    ]
    permissions = next(
        config["permissions"] for config in configs if "permissions" in config
    )
    filesystem = permissions["harness-worker"]["filesystem"]
    assert filesystem[str(worker)] == "write"
    for name in (".agents", ".codex", ".aws"):
        assert filesystem[str(worker / name)] == "read"


@pytest.mark.parametrize("access", ["write", "read-only"])
def test_codex_dry_run_grants_only_the_shared_check_directories(
    dispatch: tuple[Path, Path, dict[str, object]], access: str
) -> None:
    repo, worker, _ = dispatch
    result = invoke(dispatch, "--dry-run", runtime="codex", changes={"access": access})
    assert result.returncode == 0, result.stderr
    command = json.loads(result.stdout)["command"]
    configs = [
        tomllib.loads(command[i + 1])
        for i, value in enumerate(command)
        if value == "--config"
    ]
    filesystem = next(
        c["permissions"]["harness-worker"]["filesystem"]
        for c in configs
        if "permissions" in c
    )
    assert filesystem[str(repo / ".harness/.sandboxes/runs/qa")] == "write"
    assert filesystem[str(repo / ".harness/.sandboxes/runs/tests")] == "write"
    assert str(repo / ".harness/.sandboxes/runs") not in filesystem
    assert filesystem[str(repo / ".harness/.sandboxes/logs")] == "write"
    assert filesystem[str(repo / ".harness/.sandboxes/cache/npm")] == "write"
    assert filesystem[str(repo / ".harness/.sandboxes/cache/ms-playwright")] == "write"
    assert filesystem[str(worker)] == ("write" if access == "write" else "read")
    assert str(repo / ".harness/.sandboxes") not in filesystem
    assert str(repo / ".harness/.sandboxes/worktrees") not in filesystem
    assert str(repo / ".harness/.sandboxes/cache") not in filesystem
    assert str(repo / ".harness/.sandboxes/scratch") not in filesystem
    assert str(repo / ".harness/.sandboxes/pr_body") not in filesystem
    for name in ("runs", "logs", "cache"):
        assert not (repo / ".harness/.sandboxes" / name).exists()


def codex_write_grants(result: subprocess.CompletedProcess[str]) -> dict[str, str]:
    command = json.loads(result.stdout)["command"]
    configs = [
        tomllib.loads(command[i + 1])
        for i, value in enumerate(command)
        if value == "--config"
    ]
    return next(
        c["permissions"]["harness-worker"]["filesystem"]
        for c in configs
        if "permissions" in c
    )


def redirect(path: Path, target: Path) -> None:
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")


def test_codex_skips_a_redirected_shared_cache_with_a_warning(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    sandboxes = repo / ".harness/.sandboxes"
    (sandboxes / "cache").mkdir()
    outside = repo.parent / "outside"
    outside.mkdir()
    redirect(sandboxes / "cache/ms-playwright", outside)

    result = invoke(dispatch, "--dry-run", runtime="codex")

    assert result.returncode == 0, result.stderr
    filesystem = codex_write_grants(result)
    assert str(sandboxes / "cache/ms-playwright") not in filesystem
    for name in ("runs/qa", "runs/tests", "logs", "cache/npm"):
        assert filesystem[str(sandboxes / name)] == "write"
    assert "warning: symlink not granted" in result.stderr
    assert str(sandboxes / "cache/ms-playwright") in result.stderr
    assert not list(outside.iterdir())


@pytest.mark.parametrize("mode", ["--dry-run", "launch"])
def test_codex_refuses_a_redirected_sandboxes_root(
    dispatch: tuple[Path, Path, dict[str, object]], mode: str
) -> None:
    repo, _, _ = dispatch
    sandboxes = repo / ".harness/.sandboxes"
    outside = repo.parent / "outside-sandboxes"
    sandboxes.rename(outside)
    redirect(sandboxes, outside)
    args = ["--dry-run"] if mode == "--dry-run" else ["--codex-bin", "/nonexistent"]

    result = invoke(dispatch, *args, runtime="codex", changes=SUPERVISED)

    assert result.returncode != 0
    assert "required path is a symlink" in result.stderr
    assert str(sandboxes) in result.stderr
    assert "Errno" not in result.stderr
    assert sorted(path.name for path in outside.iterdir()) == ["scratch"]


@pytest.mark.parametrize(
    "role,access,required",
    [("developer", "write", True), ("code-review", "read-only", False)],
)
def test_codex_runs_tests_is_required_only_for_a_developer(
    dispatch: tuple[Path, Path, dict[str, object]],
    role: str,
    access: str,
    required: bool,
) -> None:
    repo, _, _ = dispatch
    runs = repo / ".harness/.sandboxes/runs"
    runs.mkdir()
    outside = repo.parent / "outside"
    outside.mkdir()
    redirect(runs / "tests", outside)

    result = invoke(
        dispatch,
        "--dry-run",
        runtime="codex",
        changes={"role": role, "access": access},
    )

    assert str(runs / "tests") in result.stderr
    if required:
        assert result.returncode != 0
        assert "required path is a symlink" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "symlink not granted" in result.stderr
        filesystem = codex_write_grants(result)
        assert str(runs / "tests") not in filesystem
        assert filesystem[str(runs / "qa")] == "write"
    assert not list(outside.iterdir())


@pytest.mark.parametrize("mode", ["--dry-run", "launch"])
def test_codex_refuses_a_required_path_that_is_a_regular_file(
    dispatch: tuple[Path, Path, dict[str, object]], mode: str
) -> None:
    repo, _, _ = dispatch
    runs = repo / ".harness/.sandboxes/runs"
    runs.mkdir()
    (runs / "qa").write_text("not a directory", encoding="utf-8")
    args = ["--dry-run"] if mode == "--dry-run" else ["--codex-bin", "/nonexistent"]

    result = invoke(
        dispatch,
        *args,
        runtime="codex",
        changes={"role": "code-review", "access": "read-only", **SUPERVISED},
    )

    assert result.returncode != 0
    assert "required path is not a directory" in result.stderr
    assert str(runs / "qa") in result.stderr
    assert "Errno" not in result.stderr
    assert (runs / "qa").read_text(encoding="utf-8") == "not a directory"


def test_codex_refuses_a_redirected_report_inbox(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    inbox = repo / ".harness/.sandboxes/scratch/inbox"
    outside = repo.parent / "outside-inbox"
    inbox.rename(outside)
    redirect(inbox, outside)

    result = invoke(dispatch, "--dry-run", runtime="codex")

    assert result.returncode != 0
    assert "required path is a symlink" in result.stderr
    assert str(inbox) in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable")
def test_codex_skips_a_shared_leaf_that_is_a_regular_file(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    logs = repo / ".harness/.sandboxes/logs"
    logs.write_text("not a directory", encoding="utf-8")

    dry = invoke(dispatch, "--dry-run", runtime="codex")

    assert dry.returncode == 0, dry.stderr
    filesystem = codex_write_grants(dry)
    assert str(logs) not in filesystem
    assert filesystem[str(repo / ".harness/.sandboxes/runs/qa")] == "write"
    assert str(logs) in dry.stderr
    assert "warning: non-directory not granted" in dry.stderr
    binary = fake_app_server(
        repo,
        worker,
        after_turn="""\
        note('turn/completed', {'turn': {'status': 'completed'}})
""",
    )

    result = invoke(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == 0, result.stderr
    assert "Errno" not in result.stderr
    assert str(logs) in result.stderr
    assert logs.read_text(encoding="utf-8") == "not a directory"


def test_codex_skips_a_shared_directory_redirected_while_it_is_created(
    dispatch: tuple[Path, Path, dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _, _ = dispatch
    sandboxes = repo / ".harness/.sandboxes"
    outside = repo.parent / "outside"
    outside.mkdir()
    redirect(repo.parent / "probe-link", outside)
    real_mkdir = Path.mkdir

    def racing_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        # Another process plants a symlink after the check and before this mkdir.
        if self == sandboxes / "cache" and not os.path.lexists(self):
            self.symlink_to(outside, target_is_directory=True)
        real_mkdir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "mkdir", racing_mkdir)

    granted = codex_worker.shared_artifact_dirs(repo, "developer", create=True)

    assert sandboxes / "cache/npm" not in granted
    assert sandboxes / "cache/ms-playwright" not in granted
    assert sandboxes / "runs/qa" in granted
    assert sandboxes / "logs" in granted
    assert not list(outside.iterdir())


@pytest.mark.parametrize("mode", ["enabled", "disabled"])
def test_codex_network_policy_requires_an_explicit_adapter_choice(
    dispatch: tuple[Path, Path, dict[str, object]], mode: str
) -> None:
    result = invoke(dispatch, "--dry-run", "--network-access", mode, runtime="codex")
    assert result.returncode == 0, result.stderr
    command = json.loads(result.stdout)["command"]
    configs = [
        tomllib.loads(command[i + 1])
        for i, value in enumerate(command)
        if value == "--config"
    ]
    network = next(
        c["permissions"]["harness-worker"]["network"]
        for c in configs
        if "permissions" in c
    )
    assert network["enabled"] is (mode == "enabled")


@pytest.mark.parametrize("linked", [False, True])
def test_codex_writer_can_commit_without_editing_git_config_or_hooks(
    dispatch: tuple[Path, Path, dict[str, object]], linked: bool
) -> None:
    repo, original, brief = dispatch
    worker = original
    if linked:
        worker = original.parent / "linked-worker"
        subprocess.run(
            [
                "git",
                "-C",
                str(original),
                "worktree",
                "add",
                "-b",
                "feature/issue-836-writer",
                str(worker),
            ],
            check=True,
            capture_output=True,
        )
    result = invoke((repo, worker, brief), "--dry-run", runtime="codex")
    assert result.returncode == 0, result.stderr
    command = json.loads(result.stdout)["command"]
    configs = [
        tomllib.loads(command[i + 1])
        for i, value in enumerate(command)
        if value == "--config"
    ]
    filesystem = next(
        c["permissions"]["harness-worker"]["filesystem"]
        for c in configs
        if "permissions" in c
    )

    def mode(path: Path) -> str:
        matches = [
            (len(Path(key).parts), value)
            for key, value in filesystem.items()
            if not key.startswith(":")
            and (path == Path(key) or Path(key) in path.parents)
        ]
        return str(max(matches, default=(0, filesystem[":root"]))[1])

    gitdir = Path(
        subprocess.check_output(
            ["git", "-C", str(worker), "rev-parse", "--absolute-git-dir"], text=True
        ).strip()
    )
    common = original / ".git"
    branch = subprocess.check_output(
        ["git", "-C", str(worker), "symbolic-ref", "HEAD"], text=True
    ).strip()
    for path in (
        gitdir / "index",
        gitdir / "index.lock",
        gitdir / "COMMIT_EDITMSG",
        gitdir / "logs/HEAD",
        common / "objects/ab/new-object",
        common / branch,
        Path(str(common / branch) + ".lock"),
        common / "logs" / branch,
        common / "packed-refs",
        common / "packed-refs.lock",
    ):
        assert mode(path) == "write", path
    for path in (
        common / "config",
        common / "hooks/pre-commit",
        worker / ".codex/config.toml",
    ):
        assert mode(path) == "read", path
    if linked:
        assert mode(worker / ".git") == "read"
        for path in (common / "index", common / "HEAD", common / "worktrees/other/index"):
            assert mode(path) == "read", path


TURN_COMPLETES_LATER = """\
        time.sleep(30)
        print(json.dumps({'method': 'turn/completed', 'params': {'turn': {'status': 'completed'}}}), flush=True)
"""


def fake_app_server(
    repo: Path,
    worker: Path,
    *,
    changes: dict[str, object] | None = None,
    after_turn: str = TURN_COMPLETES_LATER,
    probe_exit: int = 0,
) -> Path:
    """A fake `codex app-server`; `after_turn` runs once the turn/start answer is sent."""
    return fake_runtime(
        repo,
        f"""import json, os, signal, sys, time
from pathlib import Path
evidence = Path({str(repo / 'native-session.json')!r})
def note(method, params):
    print(json.dumps({{'method': method, 'params': params}}), flush=True)
if sys.argv[1] != 'app-server':
    print('legacy exec cannot expose native thread identity', flush=True)
    sys.exit(9)
for line in sys.stdin:
    request = json.loads(line)
    method = request.get('method')
    if method == 'initialize':
        result = {{}}
    elif method == 'thread/start':
        result = {{'thread': {{'id': 'thread-observed'}}, 'model': 'test-model',
                   'cwd': {str(worker)!r}, 'reasoningEffort': 'high',
                   'activePermissionProfile': {{'id': 'harness-worker'}}}}
        result.update({changes or {}!r})
    elif method == 'command/exec':
        params = request['params']
        Path({str(repo / 'native-probe.json')!r}).write_text(json.dumps(params))
        result = {{'exitCode': {probe_exit}, 'stdout': '',
                   'stderr': 'write probe refused: /worker/.git/index.lock' if {probe_exit} else ''}}
    elif method == 'turn/start':
        evidence.write_text(json.dumps({{'pid': os.getpid(), 'session': os.getsid(0),
            'pgid': os.getpgid(0), 'parent': os.getppid(),
            'cwd': os.getcwd(), 'thread': request['params']['threadId'],
            'prompt': request['params']['input'][0]['text']}}))
        result = {{'turn': {{'id': 'turn-worker', 'status': 'inProgress'}}}}
    else:
        continue
    print(json.dumps({{'id': request['id'], 'result': result}}), flush=True)
    if method == 'turn/start':
{after_turn}""",
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_codex_refuses_to_send_the_task_if_the_native_write_probe_fails(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(repo, worker, probe_exit=1)

    result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")

    assert result.returncode == 1
    assert "/worker/.git/index.lock" in result.stderr
    params = json.loads((repo / "native-probe.json").read_text())
    assert params["permissionProfile"] == "harness-worker"
    assert params["cwd"] == str(worker)
    assert not (repo / "native-session.json").exists()


@pytest.mark.skipif(
    sys.platform != "linux"
    or os.environ.get("HARNESS_NATIVE_CODEX_PROBE") != "1"
    or shutil.which("codex") is None,
    reason="opt-in Linux Codex sandbox smoke",
)
@pytest.mark.parametrize("access", ("write", "read-only"))
@pytest.mark.parametrize("nested", (False, True))
def test_codex_native_probe_respects_role_and_sibling_worktree(
    dispatch: tuple[Path, Path, dict[str, object]], access: str, nested: bool,
) -> None:
    repo, main, brief = dispatch
    if nested:
        repo = main
        inbox = repo / ".harness/.sandboxes/scratch/inbox"
        inbox.mkdir(parents=True)
        brief["report_staging_path"] = str(inbox / "dispatch-test.json")
    parent = main / ".harness/.sandboxes/worktrees" if nested else main.parent
    worker = parent / "selected"
    sibling = parent / "sibling"
    for checkout in (worker, sibling):
        subprocess.run(
            ["git", "-C", str(main), "worktree", "add", "-b", checkout.name, str(checkout)],
            check=True, capture_output=True,
        )
    brief["access"] = access
    incoming = Path(str(brief["report_staging_path"])).parent
    check_dirs = [repo / ".harness/.sandboxes" / part for part in ("runs/qa", "runs/tests", "logs")]
    for directory in (*check_dirs, repo / ".harness/orchestration/state"):
        directory.mkdir(parents=True)
    git_dir, sibling_git_dir = (
        subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--absolute-git-dir"], text=True
        ).strip()
        for path in (worker, sibling)
    )
    server = codex_worker.AppServer(codex_worker.worker_command(brief, repo, worker), worker)

    try:
        server.request("initialize", {
            "clientInfo": {"name": "harness-write-probe-smoke", "version": "1"},
            "capabilities": {"experimentalApi": True},
        })
        server.send({"method": "initialized", "params": {}})

        def probe(*paths: Path | str) -> dict[str, object]:
            result: dict[str, object] = server.request("command/exec", {
                "command": [sys.executable, str(CODEX_ADAPTER.with_name("worker_write_probe.py")),
                            *map(str, paths)],
                "permissionProfile": "harness-worker",
                "cwd": str(worker),
                "timeoutMs": 5000,
            })
            return result

        own_paths = [worker, Path(git_dir)]
        result = probe(incoming, *check_dirs, *(own_paths if access == "write" else []))
        assert result["exitCode"] == 0, result
        denied = [sibling, Path(sibling_git_dir), *(own_paths if access == "read-only" else [])]
        for path in denied:
            result = probe(path)
            assert result["exitCode"] == 1, result
            assert str(path) in str(result["stderr"])
        for path in [*own_paths, *denied, incoming, *check_dirs]:
            assert not list(path.glob(".harness-write-probe-*"))
    finally:
        server.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_codex_worker_receives_native_identity_for_its_own_thread(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(repo, worker)
    evidence = repo / "native-session.json"
    try:
        result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")

        assert result.returncode == 0, result.stderr
        data = json.loads(evidence.read_text())
        assert data["cwd"] == str(worker)
        assert data["thread"] == "thread-observed"
        assert "thread/start" in data["prompt"]
        assert "thread-observed" in data["prompt"]
        assert '"model": "test-model"' in data["prompt"]
        assert "dispatch self-report" in data["prompt"]
    finally:
        if evidence.exists():
            os.kill(json.loads(evidence.read_text())["pid"], 15)


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"model": "different-model"}, "model"),
        ({"model": None}, "model"),
        ({"cwd": "/other-checkout"}, "cwd"),
        ({"reasoningEffort": "low"}, "reasoningEffort"),
        ({"activePermissionProfile": {"id": ":workspace"}}, "permission profile"),
        ({"thread": {}}, "thread identity"),
    ],
)
def test_codex_rejects_native_mismatch_before_sending_worker_task(
    dispatch: tuple[Path, Path, dict[str, object]],
    changes: dict[str, object],
    reason: str,
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(repo, worker, changes=changes)

    result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")

    assert result.returncode == 1
    assert reason in result.stderr
    assert not (repo / "native-session.json").exists()


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"role": "qa"}, "role qa"),
        ({"purpose": "publish"}, "purpose publish"),
        ({"resolved_transport": "in-process"}, "external"),
        ({"allowed_tools": None}, "allowed_tools"),
        ({"allowed_tools": []}, "allowed_tools"),
        ({"access": "unknown"}, "access"),
    ],
)
def test_codex_rejects_unsupported_briefs(
    dispatch: tuple[Path, Path, dict[str, object]],
    changes: dict[str, object],
    reason: str,
) -> None:
    result = invoke(dispatch, "--dry-run", runtime="codex", changes=changes)
    assert result.returncode == 1
    assert reason in result.stderr


@pytest.mark.parametrize("code", [0, 7])
@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_codex_reports_early_exit_with_log_tail(
    dispatch: tuple[Path, Path, dict[str, object]], code: int
) -> None:
    binary = fake_runtime(
        dispatch[0],
        f"import sys\nsys.stdin.readline()\nprint('fake codex failure', flush=True)\nsys.exit({code})\n",
    )
    result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")
    assert result.returncode == 1
    assert (
        f"exited with {code}" in result.stderr and "fake codex failure" in result.stderr
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_codex_worker_that_dies_right_after_readiness_is_rejected(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    # The receipt says ready, then the app-server is gone at once (#1251).
    binary = fake_app_server(repo, worker, after_turn="        sys.exit(3)\n")

    result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")

    assert result.returncode == 1, result.stdout


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_codex_starts_detached_in_worker_with_stdin(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    if sys.platform == "win32":
        pytest.skip("os.getsid is POSIX-only")
    repo, worker, _ = dispatch
    evidence = repo / "native-session.json"
    binary = fake_app_server(repo, worker)
    try:
        result = invoke(dispatch, "--codex-bin", str(binary), runtime="codex")
        assert result.returncode == 0, result.stderr
        data = json.loads(evidence.read_text())
        assert data["session"] != os.getsid(0)
        assert data["cwd"] == str(worker)
        assert "report submit" in data["prompt"]
        assert data["thread"] == "thread-observed"
    finally:
        if evidence.exists():
            os.kill(json.loads(evidence.read_text())["pid"], 15)


def harness_events(stdout: str) -> list[tuple[object, object]]:
    """Every stdout line must be a harness-event; return (kind, text) pairs."""
    records = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    assert all(record["type"] == "harness-event" for record in records), records
    return [(record["kind"], record["text"]) for record in records]


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable")
def test_codex_prepares_check_directories_before_the_app_server_starts(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    sandboxes = repo / ".harness/.sandboxes"
    binary = fake_app_server(
        repo,
        worker,
        after_turn=f"""\
        for name in ('runs/qa', 'runs/tests', 'logs', 'cache/npm', 'cache/ms-playwright'):
            (Path({str(sandboxes)!r}) / name / 'runner.txt').write_text('ready')
        note('turn/completed', {{'turn': {{'status': 'completed'}}}})
""",
    )

    result = invoke(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_codex_supervised_serves_the_turn_in_the_adapter_group_and_streams_events(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(
        repo,
        worker,
        after_turn="""\
        note('item/started', {'item': {'id': 'cmd-1', 'type': 'commandExecution',
                                       'command': 'cat secret.txt'}})
        note('item/started', {'item': {'id': 'reason-1', 'type': 'reasoning'}})
        note('item/reasoning/textDelta', {'itemId': 'reason-1', 'delta': 'private thought'})
        note('item/agentMessage/delta', {'itemId': 'msg-1', 'delta': 'Hello, '})
        note('item/agentMessage/delta', {'itemId': 'msg-1', 'delta': 'world'})
        note('item/completed', {'item': {'id': 'msg-1', 'type': 'agentMessage'}})
        note('item/agentMessage/delta', {'itemId': 'msg-2', 'delta': 'Unfinished tail'})
        note('turn/completed', {'turn': {'status': 'completed'}})
""",
    )

    result, adapter_pid = run_in_own_group(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == 0, result.stderr
    data = json.loads((repo / "native-session.json").read_text())
    # The app-server is the adapter's own child in the adapter's group: no detached re-exec.
    assert data["parent"] == adapter_pid
    assert data["pgid"] == adapter_pid
    assert data["cwd"] == str(worker)
    assert "dispatch self-report" in data["prompt"]
    assert harness_events(result.stdout) == [
        ("system", "Runtime session connected"),
        ("tool", "commandExecution"),
        ("output", "Hello, world"),
        ("output", "Unfinished tail"),
        ("result", "Turn completed"),
    ]
    assert "cat secret.txt" not in result.stdout
    assert "private thought" not in result.stdout
    assert not (repo / ".harness/.sandboxes/scratch/worker-logs").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and signals")
@pytest.mark.parametrize(
    "after_turn,code",
    [
        ("        sys.exit(7)\n", 7),
        ("        os.kill(os.getpid(), signal.SIGTERM)\n", 128 + signal.SIGTERM),
        ("        sys.exit(0)\n", 1),
    ],
    ids=["exit-7", "sigterm", "exit-0-before-completion"],
)
def test_codex_supervised_returns_the_app_server_exit_status(
    dispatch: tuple[Path, Path, dict[str, object]], after_turn: str, code: int
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(repo, worker, after_turn=after_turn)

    result, _ = run_in_own_group(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == code, result.stderr
    assert harness_events(result.stdout) == [("system", "Runtime session connected")]


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable")
def test_codex_supervised_reports_a_turn_that_did_not_complete_as_an_error(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(
        repo,
        worker,
        after_turn="""\
        note('turn/completed', {'turn': {'status': 'failed'}})
        time.sleep(30)
""",
    )

    result, _ = run_in_own_group(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == 1
    assert harness_events(result.stdout)[-1] == ("error", "Turn failed")


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable")
def test_codex_supervised_streams_a_worker_error_and_fails(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    binary = fake_app_server(
        repo,
        worker,
        after_turn="""\
        note('error', {'error': {'message': 'model overloaded'}, 'willRetry': False})
        time.sleep(30)
""",
    )

    result, _ = run_in_own_group(
        dispatch, "--codex-bin", str(binary), runtime="codex", changes=SUPERVISED
    )

    assert result.returncode == 1
    assert harness_events(result.stdout)[-1] == ("error", "model overloaded")


def test_codex_dispatch_help_exposes_adapter_arguments(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    result = invoke(dispatch, "--help", runtime="codex")
    assert result.returncode == 0
    for flag in (
        "--repo",
        "--brief",
        "--extra-prompt-file",
        "--codex-bin",
        "--network-access",
    ):
        assert flag in result.stdout


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable")
def test_claude_code_runs_the_worker_in_the_foreground_under_the_runtime_supervisor(
    external_worker: recovery_tests.RecoveryTests, claude_endpoint: str
) -> None:
    batch = external_worker._create_batch()
    result = external_worker._dispatch(batch["batch_id"], "architect")
    runtime = external_worker.tmp / "fake-claude"
    runtime.write_text(
        "#!/usr/bin/env python3\nimport json,sys\n"
        "if '--help' in sys.argv:\n print('--verbose --output-format --model --effort --permission-mode --session-id --tools manual --input-format --permission-prompts');sys.exit(0)\n"
        "init=json.loads(sys.stdin.readline())\n"
        "print(json.dumps({'type':'control_response','response':{'subtype':'success','request_id':init['request_id'],'response':{}}}),flush=True)\n"
        "sys.stdin.readline()\nsys.exit(3)\n"
    )
    runtime.chmod(0o755)
    brief = (
        external_worker._records() / "dispatches" / (result["dispatch_id"] + ".json")
    )

    process = subprocess.run(
        [
            sys.executable,
            str(claude_adapter.ADAPTER),
            "dispatch",
            "--repo",
            str(external_worker.repo),
            "--brief",
            str(brief),
            "--runtime-executable",
            str(runtime),
            "--visibility=background",
            "--endpoint",
            claude_endpoint,
        ],
        env={
            **os.environ,
            "HARNESS_OPERATION_ID": "operation-of-the-runtime",
            "HARNESS_DISPATCH_ID": result["dispatch_id"],
        },
        capture_output=True,
        text=True,
        timeout=15,
    )

    # The adapter returned only after its worker ended, and exits with the worker's code.
    assert process.returncode == 3, process.stderr or process.stdout
    receipt = json.loads(process.stdout)
    assert receipt["worker_exit_code"] == 3
    terminal = json.loads(Path(receipt["terminal_path"]).read_text())
    assert terminal["exit_code"] == 3
    assert not (Path(receipt["terminal_path"]).parent / "supervisor.log").exists()


class _SubprocessWith:
    """The subprocess module with some attributes replaced."""

    def __init__(self, **replaced: object) -> None:
        self.replaced = replaced

    def __getattr__(self, name: str) -> object:
        return self.replaced[name] if name in self.replaced else getattr(subprocess, name)


class StuckProcess:
    """A worker process that never becomes ready and records how it was stopped."""

    pid = 424242

    def __init__(self) -> None:
        self.stopped_by: list[str] = []
        self.stdin = self

    def write(self, data: bytes) -> int:
        return len(data)

    def close(self) -> None:
        pass

    def poll(self) -> None:
        return None

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def terminate(self) -> None:
        self.stopped_by.append("terminate")


@pytest.mark.parametrize(
    "platform,stopped_by",
    [("win32", ["terminate"]), ("linux", ["killpg"])],
)
def test_codex_stops_a_stuck_worker_by_group_only_where_posix_groups_exist(
    dispatch: tuple[Path, Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    stopped_by: list[str],
) -> None:
    repo, worker, brief = dispatch
    path = repo / "brief.json"
    path.write_text(json.dumps(brief), encoding="utf-8")
    process = StuckProcess()

    def killpg(pid: int, number: int) -> None:
        process.stopped_by.append("killpg")
        assert (pid, number) == (process.pid, signal.SIGTERM)

    monkeypatch.chdir(worker)
    monkeypatch.setattr(sys, "platform", platform)
    # Windows has no os.killpg: the stand-in must not exist there, and is never a real group.
    monkeypatch.setattr(os, "killpg", killpg, raising=False)
    # Only the adapter's own Popen is replaced; its `git` calls still run for real.
    monkeypatch.setattr(
        codex_worker,
        "subprocess",
        _SubprocessWith(Popen=lambda *a, **k: process),
    )
    # A negative window ends the readiness wait at once.
    monkeypatch.setattr(codex_worker, "STARTUP_CHECK_SECONDS", -2)
    args = codex_worker.argparse.Namespace(
        repo=str(repo),
        brief=str(path),
        codex_bin="codex",
        network_access="disabled",
        extra_prompt_file=None,
        dry_run=False,
    )

    assert codex_worker.start(args) == 1
    assert process.stopped_by == stopped_by


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="POSIX permissions that bind the test user",
)
@pytest.mark.parametrize("shared", ("objects", "refs"))
def test_writer_probe_refuses_read_only_common_git_storage_of_a_linked_worktree(
    dispatch: tuple[Path, Path, dict[str, object]], shared: str
) -> None:
    from harness.adapters import worker_write_probe

    repo, main, brief = dispatch
    linked = main.parent / "linked"
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-b", "linked", str(linked)],
        check=True, capture_output=True,
    )
    common = main / ".git"
    incoming = Path(str(brief["report_staging_path"])).parent
    targets = worker_write_probe.write_targets(linked, incoming, [], writer=True)
    assert str(common / "objects") in targets and str(common / "refs") in targets
    (common / shared).chmod(0o555)
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "harness/adapters/worker_write_probe.py"), *targets],
            capture_output=True, text=True, check=False,
        )
    finally:
        (common / shared).chmod(0o755)
    assert result.returncode == 1
    assert f"write probe refused: {common / shared}" in result.stderr


CLAUDE_RUNS_PROBE = """\
import json, os, subprocess, sys, time
from pathlib import Path
def emit(event):
    print(json.dumps(event), flush=True)
command = json.loads(sys.stdin.readline())['message']['content'].splitlines()[-1]
emit({'type': 'system', 'subtype': 'init'})
emit({'type': 'assistant', 'message': {'content': [
    {'type': 'tool_use', 'id': 'probe', 'name': 'Bash', 'input': {'command': command}},
]}})
time.sleep(DELAY)
done = subprocess.run(command, shell=True, capture_output=True, text=True)
emit({'type': 'user', 'message': {'content': [
    {'type': 'tool_result', 'tool_use_id': 'probe', 'is_error': done.returncode != 0,
     'content': done.stdout + done.stderr},
]}})
emit({'type': 'result', 'subtype': 'success', 'is_error': False})
prompt = json.loads(sys.stdin.readline())['message']['content']
"""


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_detached_waits_for_a_slow_probe_refusal_and_reports_its_path(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    git_dir = worker / ".git"
    git_dir.chmod(0o555)
    binary = fake_runtime(
        repo,
        CLAUDE_RUNS_PROBE.replace("DELAY", "4")
        + f"Path({str(repo / 'unexpected-task')!r}).touch()\n",
    )
    try:
        result = invoke(dispatch, "--claude-bin", str(binary))
    finally:
        git_dir.chmod(0o755)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("root ignores directory permissions")
    assert result.returncode == 1
    assert f"write probe refused: {git_dir}" in result.stderr
    assert not (repo / "unexpected-task").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_detached_returns_after_a_slow_successful_probe(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    evidence = repo / "task.txt"
    binary = fake_runtime(
        repo,
        CLAUDE_RUNS_PROBE.replace("DELAY", "4")
        + f"Path({str(evidence)!r}).write_text(str(os.getpid()))\ntime.sleep(30)\n",
    )
    try:
        result = invoke(dispatch, "--claude-bin", str(binary))
        assert result.returncode == 0, result.stderr
        assert evidence.exists()
    finally:
        if evidence.exists():
            os.kill(int(evidence.read_text()), 15)


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_creates_runner_and_cache_directories_on_a_fresh_install(
    dispatch: tuple[Path, Path, dict[str, object]], tmp_path: Path,
) -> None:
    repo, _, _ = dispatch
    cache = tmp_path / "fresh-cache/uv"
    binary = fake_runtime(repo, CLAUDE_RUNS_PROBE.replace("DELAY", "0") + "sys.exit(0)\n")
    runs = repo / ".harness/.sandboxes/runs"
    assert not runs.exists()

    result, _ = run_in_own_group(
        dispatch, "--claude-bin", str(binary),
        changes={
            **SUPERVISED,
            "allowed_tools": ["Read", "Bash", "Edit", "Agent(test-author)"],
            "runtime_access": {"filesystem": [
                {"resource": "cache", "access": "write", "path": str(cache)},
            ]},
        },
    )

    assert result.returncode == 0, result.stderr
    assert runs.is_dir() and cache.is_dir()
    assert not list(runs.glob(".harness-write-probe-*"))


def test_claude_refuses_a_symlinked_check_directory(
    dispatch: tuple[Path, Path, dict[str, object]], tmp_path: Path,
) -> None:
    repo, _, _ = dispatch
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (repo / ".harness/.sandboxes/runs").symlink_to(elsewhere)
    result, _ = run_in_own_group(
        dispatch, "--claude-bin", "/fake/claude",
        changes={**SUPERVISED, "allowed_tools": ["Read", "Bash", "Agent(test-author)"]},
    )
    assert result.returncode == 1
    assert "symlink" in result.stderr


def test_claude_dry_run_creates_no_check_directory(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    result = invoke(
        dispatch, "--dry-run", "--claude-bin", "/fake/claude",
        changes={"allowed_tools": ["Read", "Bash", "Agent(test-author)"]},
    )
    assert result.returncode == 0, result.stderr
    assert not (repo / ".harness/.sandboxes/runs").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_probe_failure_names_its_cause_without_secrets(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    binary = fake_runtime(
        repo,
        CLAUDE_PROBE.replace(
            "'content': 'Harness write probe passed'",
            "'is_error': True, 'content': 'bwrap: setting up uid map: Permission denied "
            "API_TOKEN=' + os.environ['FAKE_API_TOKEN']",
        ),
    )
    os.environ["FAKE_API_TOKEN"] = "s3cr3t-value-123"
    try:
        result, _ = run_in_own_group(dispatch, "--claude-bin", str(binary), changes=SUPERVISED)
    finally:
        del os.environ["FAKE_API_TOKEN"]

    assert result.returncode == 1
    assert "bwrap: setting up uid map: Permission denied" in result.stderr
    assert "s3cr3t-value-123" not in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_reports_a_denied_bash_probe_from_the_result_event(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    binary = fake_runtime(
        repo,
        "import json, sys\n"
        "sys.stdin.readline()\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}), flush=True)\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,\n"
        "    'result': 'PreToolUse hook blocked the command',\n"
        "    'permission_denials': [{'tool_name': 'Bash', 'tool_use_id': 'x',\n"
        "                            'tool_input': {'command': 'echo private'}}]}), flush=True)\n",
    )
    result, _ = run_in_own_group(dispatch, "--claude-bin", str(binary), changes=SUPERVISED)
    assert result.returncode == 1
    assert "PreToolUse hook blocked the command" in result.stderr
    assert "denied the Bash tool" in result.stderr
    assert "echo private" not in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process group")
def test_claude_reports_the_runtime_stderr_when_it_exits_before_the_probe(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, _, _ = dispatch
    binary = fake_runtime(
        repo,
        "import sys\nsys.stdin.readline()\n"
        "print('Error: invalid settings in .claude/settings.json', file=sys.stderr, flush=True)\n"
        "sys.exit(3)\n",
    )
    result, _ = run_in_own_group(dispatch, "--claude-bin", str(binary), changes=SUPERVISED)
    assert result.returncode == 3
    assert "exited with 3 before the native write probe finished" in result.stderr
    assert "invalid settings in .claude/settings.json" in result.stderr


def test_claude_refuses_a_tool_policy_without_plain_bash_up_front(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    result = invoke(
        dispatch, "--dry-run", "--claude-bin", "/fake/claude",
        changes={"role": "code-review", "access": "read-only",
                 "allowed_tools": ["Read", "Grep", "Bash(git diff:*)"]},
    )
    assert result.returncode == 1
    assert "plain Bash" in result.stderr
