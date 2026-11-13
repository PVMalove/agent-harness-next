"""The runtime autostart through the hooks ``harness init`` installs (ADR 0031; DoD 6, 7, 9).

A scratch project gets the engineering-suite install, a release build of ``harness-runtime`` in
``native/harness-runtime/target/release`` with its dep-info and a migrated store. Every
``PreToolUse(Bash)``, ``Stop`` and ``SubagentStop`` handler of the installed
``.claude/settings.local.json`` runs as Claude Code runs it: ``/bin/sh -c`` in a new session with
the payload on stdin. In the standard and the strict profile nothing of the autostart blocks, the
runtime starts, is reused and stops after the last owner left; a manual or busy runtime keeps
serving, and the earlier refusals still block.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.core.test_uninstall import git, harness
from tests.orchestration.runtime_store_support import (
    SHORT_TMP,
    STATE_REL,
    autostart_message,
    build_state,
    hook_handlers,
    migrate,
    run_handler,
    runtime_binary,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="Windows keeps the manual start of the runtime"
)

AUTOSTART = "runtime-autostart.sh"


class Project:
    """An installed project with a fresh release build and a migrated store."""

    def __init__(self, root: Path, profile: str) -> None:
        self.root = root
        root.mkdir()
        git(root, "init", "-b", "main")
        installed = harness("init", str(root), "--capability", "engineering-suite")
        assert installed.returncode == 0, installed.stderr
        project_json = root / ".harness" / "project.json"
        data = json.loads(project_json.read_text(encoding="utf-8"))
        data["hook_policy"] = {"profile": profile}
        project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        self.settings = root / ".claude" / "settings.local.json"
        self._build()
        build_state(root)
        assert migrate(root).returncode == 0
        self.xdg = Path(tempfile.mkdtemp(prefix="hr", dir=SHORT_TMP)).resolve()
        self.pids: list[int] = []

    def _build(self) -> None:
        workspace = self.root / "native" / "harness-runtime"
        source = workspace / "crates" / "harness-runtime" / "src" / "main.rs"
        source.parent.mkdir(parents=True)
        source.write_text("fn main() {}\n", encoding="utf-8")
        (workspace / "Cargo.toml").write_text("[workspace]\n", encoding="utf-8")
        (workspace / "Cargo.lock").write_text("version = 4\n", encoding="utf-8")
        binary = workspace / "target" / "release" / "harness-runtime"
        binary.parent.mkdir(parents=True)
        shutil.copy2(runtime_binary(), binary)
        os.utime(binary)
        (binary.parent / "harness-runtime.d").write_text(f"{binary}: {source}\n", encoding="utf-8")
        old = time.time() - 600
        for path in (source, workspace / "Cargo.toml", workspace / "Cargo.lock"):
            os.utime(path, (old, old))

    @property
    def env(self) -> dict[str, str]:
        return {"XDG_RUNTIME_DIR": str(self.xdg)}

    def socket_exists(self) -> bool:
        return any(self.xdg.rglob("*.sock"))

    def payload(self, event: str, command: str = "", agent: str = "") -> JsonObject:
        payload: JsonObject = {
            "session_id": "s1",
            "hook_event_name": event,
            "cwd": str(self.root),
        }
        if event == "PreToolUse":
            payload["tool_name"] = "Bash"
            payload["tool_input"] = {
                "command": command
                or "python3 .harness/orchestration/coordinator.py --repo . dispatch status"
            }
        else:
            payload["stop_hook_active"] = False
        if agent:
            payload["agent_id"] = agent
        return payload

    def fire(
        self, event: str, command: str = "", agent: str = ""
    ) -> dict[str, subprocess.CompletedProcess[str]]:
        """Every handler of ``event`` (Bash for PreToolUse); the answer of each, by its command."""
        tool = "Bash" if event == "PreToolUse" else ""
        answers = {
            handler: run_handler(
                handler, self.root, self.payload(event, command, agent), self.env
            )
            for handler in hook_handlers(self.settings, event, tool)
        }
        for handler, done in answers.items():
            if AUTOSTART in handler:
                found = re.search(r"pid (\d+)", autostart_message(done))
                if found:
                    self.pids.append(int(found.group(1)))
        return answers

    def stops_within(self, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if not self.socket_exists():
                return True
            time.sleep(0.1)
        return False

    def keeps_serving(self) -> bool:
        time.sleep(2.5)
        return self.socket_exists()

    def close(self) -> None:
        for pid in self.pids:
            if sys.platform == "win32":  # signal.SIGKILL is POSIX-only
                break
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
        shutil.rmtree(self.xdg, ignore_errors=True)


def autostart(answers: dict[str, subprocess.CompletedProcess[str]]) -> subprocess.CompletedProcess[str]:
    [done] = [done for handler, done in answers.items() if AUTOSTART in handler]
    return done


def assert_nothing_blocks(answers: dict[str, subprocess.CompletedProcess[str]]) -> None:
    for handler, done in answers.items():
        assert done.returncode == 0, (handler, done.stderr)


@pytest.fixture(params=["standard", "strict"])
def project(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Project]:
    made = Project(tmp_path / "project", request.param)
    yield made
    made.close()


def test_the_installed_hooks_start_reuse_and_stop_the_runtime(project: Project) -> None:
    started = project.fire("PreToolUse")

    assert_nothing_blocks(started)
    message = autostart_message(autostart(started))
    assert "harness-runtime serve" in message and project.pids, autostart(started).stderr
    assert project.socket_exists()
    [pid] = project.pids

    reused = project.fire("PreToolUse")
    subagent = project.fire("PreToolUse", agent="a1")
    assert_nothing_blocks(reused)
    assert autostart(reused).stdout.strip() == ""
    assert autostart(subagent).stdout.strip() == ""
    assert project.pids == [pid]

    assert_nothing_blocks(project.fire("SubagentStop", agent="a1"))
    stopped = project.fire("Stop")
    assert_nothing_blocks(stopped)
    assert autostart(stopped).stdout.strip() == ""
    assert project.stops_within(10), "the own runtime did not stop after the last owner left"


def test_the_runtime_survives_the_end_of_the_hook_process_group(project: Project) -> None:
    started = project.fire("PreToolUse")
    [pid] = project.pids
    if sys.platform == "win32":
        pytest.skip("os.getpgid is POSIX-only")
    group = os.getpgid(pid)

    # The hook ran in its own session; the runtime is in a process group of its own.
    assert group == pid
    for done in started.values():
        assert done.returncode == 0
    assert project.keeps_serving()


def test_a_manual_runtime_is_reused_and_never_stopped(project: Project) -> None:
    manual = subprocess.Popen(
        [str(runtime_binary()), "serve", "--repo", str(project.root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, **project.env},
    )
    try:
        assert manual.stdout is not None
        assert "ready" in manual.stdout.readline()

        answers = project.fire("PreToolUse")
        assert_nothing_blocks(answers)
        assert autostart(answers).stdout.strip() == ""
        assert_nothing_blocks(project.fire("Stop"))

        assert project.keeps_serving()
        assert manual.poll() is None
    finally:
        manual.kill()
        manual.wait(timeout=30)


def test_a_busy_store_keeps_the_own_runtime_until_it_is_idle(project: Project) -> None:
    project.fire("PreToolUse")
    database = project.root / STATE_REL / "runtime.db"
    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("INSERT INTO qa_queue (id, body_json) VALUES ('q1', '{}')")
        connection.commit()

    assert_nothing_blocks(project.fire("Stop"))
    assert project.keeps_serving(), "a queued QA run must keep the runtime"

    with contextlib.closing(sqlite3.connect(database)) as connection:
        connection.execute("DELETE FROM qa_queue")
        connection.commit()
    assert project.stops_within(10)


@pytest.mark.parametrize(
    "command",
    [
        "python3 .harness/orchestration/coordinator.py --repo . status && git push --force origin main",
        "python3 .harness/orchestration/coordinator.py --repo . status; git reset --hard HEAD~1",
    ],
)
def test_the_earlier_refusals_still_block_next_to_the_autostart(
    project: Project, command: str
) -> None:
    answers = project.fire("PreToolUse", command)

    blocked = [handler for handler, done in answers.items() if done.returncode == 2]
    assert blocked, {handler: done.stderr for handler, done in answers.items()}
    assert all(AUTOSTART not in handler for handler in blocked)
    assert autostart(answers).returncode == 0


def test_the_second_runtime_gets_no_autostart(project: Project) -> None:
    codex = project.root / ".codex" / "hooks.json"

    assert codex.is_file()
    assert AUTOSTART not in codex.read_text(encoding="utf-8")
    for event in ("PreToolUse", "Stop", "SubagentStop"):
        tool = "Bash" if event == "PreToolUse" else ""
        assert any(AUTOSTART in handler for handler in hook_handlers(project.settings, event, tool))
