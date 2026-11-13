"""External worker adapters exercised only with dry runs and fake runtimes."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
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


@pytest.mark.parametrize("code", [0, 7])
@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_reports_any_early_exit_with_log_tail(
    dispatch: tuple[Path, Path, dict[str, object]], code: int
) -> None:
    binary = fake_runtime(
        dispatch[0],
        f"import sys\nsys.stdin.read()\nprint('fake startup failure', flush=True)\nsys.exit({code})\n",
    )
    result = invoke(dispatch, "--claude-bin", str(binary))
    assert result.returncode == 1
    assert f"exited with {code}" in result.stderr
    assert "fake startup failure" in result.stderr


@pytest.mark.skipif(os.name == "nt", reason="POSIX fake executable and process session")
def test_claude_starts_detached_with_stdin_prompt_in_worker_checkout(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    repo, worker, _ = dispatch
    evidence = repo / "started.json"
    body = f"import json, os, sys, time\nfrom pathlib import Path\nprompt = sys.stdin.read()\nPath({str(evidence)!r}).write_text(json.dumps(dict(pid=os.getpid(), session=os.getsid(0), cwd=os.getcwd(), prompt=prompt, args=sys.argv[1:])))\ntime.sleep(30)\n"
    binary = fake_runtime(repo, body)
    try:
        started = time.monotonic()
        result = invoke(dispatch, "--claude-bin", str(binary))
        assert result.returncode == 0, result.stderr
        assert time.monotonic() - started < 10
        data = json.loads(evidence.read_text())
        assert data["pid"] == data["session"]
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
        "import json, os, sys\nfrom pathlib import Path\n"
        f"Path({str(evidence)!r}).write_text(json.dumps(dict(pgid=os.getpgid(0), "
        "cwd=os.getcwd(), stdin=sys.stdin.read(), args=sys.argv[1:])))\n"
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
    assert data["stdin"] == ""
    args = data["args"]
    assert args[0] == "-p"
    assert "dispatch self-report" in args[1]
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


def test_claude_supervised_refuses_a_prompt_over_the_argument_bound(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    extra = dispatch[0] / "retry.txt"
    extra.write_text("x" * 130000, encoding="utf-8")
    result = invoke(
        dispatch,
        "--claude-bin",
        "/fake/claude",
        "--extra-prompt-file",
        str(extra),
        changes=SUPERVISED,
    )
    assert result.returncode == 1
    assert "shorten --extra-prompt-file" in result.stderr


def test_claude_supervised_dry_run_puts_the_prompt_right_after_print_flag(
    dispatch: tuple[Path, Path, dict[str, object]],
) -> None:
    result = invoke(
        dispatch, "--dry-run", "--claude-bin", "/fake/claude", changes=SUPERVISED
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    command = data["command"]
    assert command[0:3] == ["/fake/claude", "-p", data["prompt"]]
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
def test_codex_bounded_checks_can_write_shared_temporary_data_and_logs(
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
    assert filesystem[str(worker)] == ("write" if access == "write" else "read")
    assert str(repo / ".harness/.sandboxes") not in filesystem
    assert str(repo / ".harness/.sandboxes/worktrees") not in filesystem


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


def fake_app_server(
    repo: Path, worker: Path, *, changes: dict[str, object] | None = None
) -> Path:
    return fake_runtime(
        repo,
        f"""import json, os, sys, time
from pathlib import Path
evidence = Path({str(repo / 'native-session.json')!r})
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
    elif method == 'turn/start':
        evidence.write_text(json.dumps({{'pid': os.getpid(), 'session': os.getsid(0),
            'cwd': os.getcwd(), 'thread': request['params']['threadId'],
            'prompt': request['params']['input'][0]['text']}}))
        result = {{'turn': {{'id': 'turn-worker', 'status': 'inProgress'}}}}
    else:
        continue
    print(json.dumps({{'id': request['id'], 'result': result}}), flush=True)
    if method == 'turn/start':
        time.sleep(30)
        print(json.dumps({{'method': 'turn/completed', 'params': {{'turn': {{'status': 'completed'}}}}}}), flush=True)
""",
    )


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
        env={**os.environ, "HARNESS_OPERATION_ID": "operation-of-the-runtime"},
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
