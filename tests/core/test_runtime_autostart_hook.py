"""Hook ``runtime-autostart`` (ADR 0031, раздел 5) с поддельным бинарником ``harness-runtime``.

Hook запускается так же, как его запускает Claude Code: ``bash runtime-autostart.sh`` установленной
копии с payload события в stdin, через конверт ``hook_response.py``. Поддельный бинарник
записывает аргументы и окружение и отвечает заданной строкой JSON и кодом.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.orchestration.hook_policy import parse_hook_response

HOOKS = Path(__file__).resolve().parents[2] / "harness" / "project" / "hooks"
BASH = shutil.which("bash") or "bash"
GIT = shutil.which("git") or "git"
pytestmark = [
    pytest.mark.skipif(
        shutil.which("bash") is None or shutil.which("git") is None,
        reason="the hook runs bash and git",
    ),
    pytest.mark.skipif(sys.platform == "win32", reason="Windows keeps the manual start"),
]

FAKE = """#!/bin/bash
{
  printf 'ARGS'; printf ' %s' "$@"; printf '\\n'
  env | sed 's/^/ENV /'
} >> "$FAKE_RECORD"
printf '%s\\n' "${FAKE_ANSWER:-}"
exit "${FAKE_CODE:-0}"
"""


class Setup:
    """An installed project (the hooks), a main checkout with a runtime build, a fake binary."""

    def __init__(self, tmp_path: Path) -> None:
        self.project = tmp_path / "project"
        shutil.copytree(
            HOOKS,
            self.project / ".claude" / "hooks",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.main = tmp_path / "main"
        self.main.mkdir()
        subprocess.run([GIT, "init", "-q", str(self.main)], check=True)
        self.workspace = self.main / "native" / "harness-runtime"
        self.record = tmp_path / "record.txt"
        self.bin_dir = tmp_path / "bin"
        self.bin_dir.mkdir()
        self.env = {
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "HOME": str(tmp_path),
            "FAKE_RECORD": str(self.record),
            # Claude Code sets it for every hook: the session project is the main checkout.
            "CLAUDE_PROJECT_DIR": str(self.main),
        }

    def source_build(self, *, fresh: bool = True) -> Path:
        """``native/harness-runtime`` with a release build and its dep-info."""
        source = self.workspace / "crates" / "harness-runtime" / "src" / "main.rs"
        source.parent.mkdir(parents=True)
        source.write_text("fn main() {}\n", encoding="utf-8")
        (self.workspace / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        (self.workspace / "Cargo.lock").write_text("version = 4\n", encoding="utf-8")
        (source.parents[1] / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
        binary = self.workspace / "target" / "release" / "harness-runtime"
        binary.parent.mkdir(parents=True)
        binary.write_text(FAKE, encoding="utf-8")
        binary.chmod(0o755)
        escaped = str(source).replace(" ", "\\ ")
        (binary.parent / "harness-runtime.d").write_text(
            f"{binary}: {escaped}\n", encoding="utf-8"
        )
        old = binary.stat().st_mtime - 100
        for path in (source, self.workspace / "Cargo.toml", self.workspace / "Cargo.lock",
                     source.parents[1] / "Cargo.toml"):
            os.utime(path, (old, old))
        if not fresh:
            os.utime(source, (old + 200, old + 200))
        return binary

    def on_path(self) -> Path:
        binary = self.bin_dir / "harness-runtime"
        binary.write_text(FAKE, encoding="utf-8")
        binary.chmod(0o755)
        return binary

    def run(
        self,
        payload: dict[str, object],
        answer: dict[str, object] | None = None,
        code: int = 0,
        extra: dict[str, str] | None = None,
        **variables: str,
    ) -> subprocess.CompletedProcess[str]:
        env = dict(self.env, FAKE_ANSWER=json.dumps(answer or {}), FAKE_CODE=str(code))
        env.update(extra or {})
        env.update(variables)
        return subprocess.run(
            [str(BASH), str(self.project / ".claude" / "hooks" / "runtime-autostart.sh")],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=60,
        )

    def pre_tool(self, command: str | None = None, **fields: str) -> dict[str, object]:
        coordinator = self.main / ".harness" / "orchestration" / "coordinator.py"
        return {
            "session_id": "s1",
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command or f'python3 "{coordinator}" --repo x dispatch status'},
            "cwd": str(self.main),
            **fields,
        }

    def calls(self) -> list[str]:
        if not self.record.exists():
            return []
        return [
            line[len("ARGS "):]
            for line in self.record.read_text("utf-8").splitlines()
            if line.startswith("ARGS")
        ]

    def recorded_env(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for line in self.record.read_text("utf-8").splitlines():
            if line.startswith("ENV "):
                key, _, value = line[4:].partition("=")
                found[key] = value
        return found


def verdict(done: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert done.returncode == 0, done.stderr
    return parse_hook_response(done.stderr)


def warning(done: subprocess.CompletedProcess[str]) -> str:
    answer = verdict(done)
    assert (answer["decision"], answer["reason_code"]) == ("warn", "runtime-autostart-failed")
    output = json.loads(done.stdout)
    assert output["systemMessage"] == output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    return str(answer["remedy"])


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def test_a_command_without_the_coordinator_is_left_alone(setup: Setup) -> None:
    setup.source_build()

    done = setup.run(setup.pre_tool("git status && make lint"))

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""
    assert setup.calls() == []


def test_a_fresh_build_is_ensured_for_the_session_with_the_application_pid(setup: Setup) -> None:
    binary = setup.source_build()

    done = setup.run(
        setup.pre_tool(),
        {"status": "reused", "owned": True, "pid": 7},
        CLAUDE_PID="4242",
    )

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""
    assert setup.calls() == [
        f"ensure --repo {setup.main} --session s1 --owner-pid 4242"
    ]
    assert str(binary).startswith(str(setup.main))


def test_a_subagent_is_its_own_owner(setup: Setup) -> None:
    setup.source_build()

    setup.run(setup.pre_tool(agent_id="a7"), {"status": "reused"})

    assert setup.calls() == [f"ensure --repo {setup.main} --session s1 --agent a7"]


def test_a_relative_coordinator_path_is_read_from_the_payload_directory(setup: Setup) -> None:
    setup.source_build()
    worktree = setup.main / ".harness" / ".sandboxes" / "worktrees" / "w"
    subprocess.run(
        [GIT, "-C", str(setup.main), "commit", "-q", "--allow-empty", "-m", "c"],
        check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"},
    )
    subprocess.run(
        [GIT, "-C", str(setup.main), "worktree", "add", "-q", str(worktree)], check=True
    )
    payload = setup.pre_tool("python3 .harness/orchestration/coordinator.py --repo . status")
    payload["cwd"] = str(worktree)

    setup.run(payload, {"status": "reused"})

    # A linked worktree reaches the runtime of its main checkout.
    assert setup.calls() == [f"ensure --repo {setup.main} --session s1"]


@pytest.fixture
def foreign(tmp_path: Path) -> Setup:
    """Another repository with its own runtime build, outside the session project."""
    other = Setup(tmp_path / "foreign")
    other.source_build()
    return other


def test_the_coordinator_of_another_repository_runs_no_binary(
    setup: Setup, foreign: Setup
) -> None:
    setup.source_build()
    coordinator = foreign.main / ".harness" / "orchestration" / "coordinator.py"

    remedy = warning(setup.run(setup.pre_tool(f'python3 "{coordinator}" --repo x status')))

    assert str(foreign.main) in remedy
    assert setup.calls() == []


@pytest.mark.parametrize(
    "command",
    [
        "echo {path}",
        "grep -n main {path}",
        "cd /tmp && echo {path} > /dev/null",
    ],
)
def test_a_quoted_coordinator_path_of_another_repository_runs_no_binary(
    setup: Setup, foreign: Setup, command: str
) -> None:
    setup.source_build()
    path = foreign.main / ".harness" / "orchestration" / "coordinator.py"
    payload = setup.pre_tool(command.format(path=path))
    payload["cwd"] = str(foreign.project)

    setup.run(payload, extra={"CLAUDE_PROJECT_DIR": str(setup.main)})

    assert setup.calls() == []


def test_the_session_project_comes_from_the_project_directory_never_the_cwd(
    setup: Setup, foreign: Setup
) -> None:
    setup.source_build()
    own = setup.pre_tool()
    own["cwd"] = str(foreign.main)

    setup.run(own, {"status": "reused"}, extra={"CLAUDE_PROJECT_DIR": str(setup.main)})
    assert setup.calls() == [f"ensure --repo {setup.main} --session s1"]

    setup.record.unlink()
    remedy = warning(
        setup.run(setup.pre_tool(), extra={"CLAUDE_PROJECT_DIR": str(foreign.main)})
    )
    assert str(setup.main) in remedy
    assert setup.calls() == []


@pytest.mark.parametrize("unset", [True, False], ids=["unset", "empty"])
def test_without_the_project_directory_every_repository_is_foreign(
    setup: Setup, unset: bool
) -> None:
    setup.source_build()
    if unset:
        del setup.env["CLAUDE_PROJECT_DIR"]
    else:
        setup.env["CLAUDE_PROJECT_DIR"] = ""

    # The payload cwd is the agent's: even the coordinator's own checkout there selects nothing.
    remedy = warning(setup.run(setup.pre_tool()))
    stop = setup.run(
        {"session_id": "s1", "hook_event_name": "Stop", "stop_hook_active": False,
         "cwd": str(setup.main)}
    )

    assert str(setup.main) in remedy and "не относится" in remedy
    assert verdict(stop)["decision"] == "allow" and stop.stdout == ""
    assert setup.calls() == []


def test_the_end_of_a_turn_in_another_repository_releases_nothing(
    setup: Setup, foreign: Setup
) -> None:
    setup.source_build()
    payload: dict[str, object] = {
        "session_id": "s1",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "cwd": str(foreign.main),
    }

    done = setup.run(payload, extra={"CLAUDE_PROJECT_DIR": str(setup.main)})

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""
    assert setup.calls() == []


def test_a_started_runtime_is_named_to_the_developer(setup: Setup) -> None:
    setup.source_build()

    done = setup.run(
        setup.pre_tool(),
        {"status": "started", "pid": 913, "log": "/run/x.serve.log"},
    )

    assert verdict(done)["decision"] == "allow"
    message = json.loads(done.stdout)["systemMessage"]
    assert "913" in message and "/run/x.serve.log" in message


def test_the_hook_scrubs_the_variables_the_application_adds_for_hooks(setup: Setup) -> None:
    setup.source_build()
    added = {
        name: "x"
        for name in (
            "CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION",
            "CLAUDE_CODE_SESSION_ATTENDED", "AI_AGENT", "CLAUDE_EFFORT", "TRACEPARENT",
            "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "CLAUDE_ENV_FILE",
            "COLUMNS", "LINES",
        )
    }

    added["CLAUDE_PROJECT_DIR"] = str(setup.main)

    setup.run(
        setup.pre_tool(),
        {"status": "reused"},
        extra=added,
        CLAUDE_PID="77",
        SECRET_TOKEN="kept",
    )

    env = setup.recorded_env()
    for name in [*added, "CLAUDE_PID", "HARNESS_HOOK_ENVELOPE"]:
        assert name not in env, name
    assert env["SECRET_TOKEN"] == "kept"
    assert env["PATH"].startswith(str(setup.bin_dir))


@pytest.mark.parametrize("touched", ["source", "Cargo.lock", "member Cargo.toml", "dep-info"])
def test_a_stale_build_only_attaches_and_is_never_started(setup: Setup, touched: str) -> None:
    binary = setup.source_build()
    newer = binary.stat().st_mtime + 50
    if touched == "dep-info":
        (binary.parent / "harness-runtime.d").unlink()
    else:
        path = {
            "source": setup.workspace / "crates" / "harness-runtime" / "src" / "main.rs",
            "Cargo.lock": setup.workspace / "Cargo.lock",
            "member Cargo.toml": setup.workspace / "crates" / "harness-runtime" / "Cargo.toml",
        }[touched]
        os.utime(path, (newer, newer))

    done = setup.run(setup.pre_tool(), {"status": "not_running"}, code=3)

    assert setup.calls() == [f"ensure --repo {setup.main} --session s1 --attach-only"]
    remedy = warning(done)
    assert "устарела" in remedy and "cargo build --release" in remedy


def test_a_stale_build_reuses_a_runtime_that_already_serves(setup: Setup) -> None:
    setup.source_build(fresh=False)

    done = setup.run(setup.pre_tool(), {"status": "reused", "owned": False})

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""


def test_an_unbuilt_workspace_names_the_build_command(setup: Setup) -> None:
    (setup.workspace).mkdir(parents=True)
    (setup.workspace / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
    setup.on_path()

    remedy = warning(setup.run(setup.pre_tool()))

    assert "не собран" in remedy and "cargo build --release" in remedy
    assert setup.calls() == []


def test_without_a_workspace_the_binary_comes_from_path(setup: Setup) -> None:
    setup.on_path()

    setup.run(setup.pre_tool(), {"status": "reused"})

    assert setup.calls() == [f"ensure --repo {setup.main} --session s1"]


def test_a_missing_binary_is_a_warning(setup: Setup) -> None:
    remedy = warning(setup.run(setup.pre_tool(), PATH="/usr/bin:/bin"))

    assert "не найден" in remedy


def test_a_refused_start_names_the_cause_and_the_journal(setup: Setup) -> None:
    setup.source_build()

    remedy = warning(
        setup.run(
            setup.pre_tool(),
            {
                "status": "refused",
                "exit_code": 2,
                "error": "the store has a newer schema",
                "remedy": "[protocol_unsupported] update harness-runtime",
                "log": "/run/x.serve.log",
            },
            code=2,
        )
    )

    assert "the store has a newer schema" in remedy
    assert "[protocol_unsupported]" in remedy
    assert "/run/x.serve.log" in remedy


def test_a_timeout_names_the_journal(setup: Setup) -> None:
    setup.source_build()

    remedy = warning(
        setup.run(setup.pre_tool(), {"status": "timeout", "seconds": 40, "log": "/l"}, code=2)
    )

    assert "40" in remedy and "/l" in remedy


def test_inside_the_agent_sandbox_the_hook_starts_nothing_and_warns(setup: Setup) -> None:
    setup.source_build()

    remedy = warning(setup.run(setup.pre_tool(), SANDBOX_RUNTIME="1"))

    assert "песочниц" in remedy
    assert setup.calls() == []


def test_windows_keeps_the_manual_start(setup: Setup) -> None:
    setup.source_build()
    uname = setup.bin_dir / "uname"
    uname.write_text("#!/bin/sh\necho MINGW64_NT-10.0\n", encoding="utf-8")
    uname.chmod(0o755)

    done = setup.run(setup.pre_tool())

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""
    assert setup.calls() == []


@pytest.mark.parametrize(
    ("event", "agent", "expected"),
    [
        ("Stop", "", "release --repo {main} --session s1"),
        ("Stop", "a1", "release --repo {main} --session s1"),
        ("SubagentStop", "a1", "release --repo {main} --session s1 --agent a1"),
    ],
)
def test_the_end_of_a_turn_releases_the_owner_silently(
    setup: Setup, event: str, agent: str, expected: str
) -> None:
    setup.source_build(fresh=False)
    payload: dict[str, object] = {
        "session_id": "s1",
        "hook_event_name": event,
        "stop_hook_active": False,
        "cwd": str(setup.main),
    }
    if agent:
        payload["agent_id"] = agent

    done = setup.run(payload, {"status": "released"}, code=1)

    assert verdict(done)["decision"] == "allow"
    assert done.stdout == ""
    assert setup.calls() == [expected.format(main=setup.main)]


def test_a_malformed_session_is_left_alone(setup: Setup) -> None:
    setup.source_build()

    done = setup.run(setup.pre_tool(session_id="a b; rm -rf /"))

    assert verdict(done)["decision"] == "allow"
    assert setup.calls() == []
