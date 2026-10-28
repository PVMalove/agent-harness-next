"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from threading import Event, Thread
from typing import cast

import pytest

from harness import cleanup
from harness.console.maintenance import load_maintenance
from harness.console import process_tree
from harness.console.runner import HarnessRuns, capturing_runner


def test_cancelled_pending_run_cannot_start_later(tmp_path: Path) -> None:
    runs = HarnessRuns()
    run = runs.reserve("pending", "pending", ["missing"], {})
    assert run is not None
    runs.abandon_pending(run)
    replacement = runs.reserve("new", "new", [], {})
    assert replacement is not None
    runs.execute(run, capturing_runner, tmp_path)
    assert run.phase == "cancelled" and replacement.phase == "pending" and runs.busy


def test_streaming_decodes_split_utf8_and_preserves_text_newlines(
    tmp_path: Path,
) -> None:
    result = capturing_runner(
        [
            sys.executable,
            "-c",
            "import os; os.write(1, b'\\xd0'); os.write(1, b'\\xaf\\r\\nend\\r'); os.write(2, b'\\xff')",
        ],
        cwd=tmp_path,
    )
    assert result.stdout == "Я\nend\n"
    assert result.stderr == "�" and result.returncode == 0


def test_capturing_runner_terminates_the_child_when_cancelled(tmp_path: Path) -> None:
    started = Event()
    cancelled = Event()
    raised: list[BaseException] = []

    def capture() -> None:
        try:
            capturing_runner(
                [
                    sys.executable,
                    "-u",
                    "-c",
                    "import time; print('ready', flush=True); time.sleep(60)",
                ],
                cwd=tmp_path,
                on_output=lambda channel, text: started.set()
                if channel == "stdout" and "ready" in text
                else None,
                cancel_event=cancelled,
            )
        except BaseException as exc:
            raised.append(exc)

    worker = Thread(target=capture)
    worker.start()
    assert started.wait(3)
    cancelled.set()
    worker.join(3)
    assert not worker.is_alive()
    assert len(raised) == 1 and isinstance(raised[0], process_tree.CommandCancelled)


def test_cancel_after_the_command_ended_keeps_its_exit_code() -> None:
    """A late cancellation must not report a finished command, and its changes, as cancelled."""
    with subprocess.Popen([sys.executable, "-c", "raise SystemExit(3)"]) as process:
        process.wait()
        cancelled = Event()
        cancelled.set()

        assert process_tree.wait_cancellable(process, cancelled, lambda: True) == 3


def test_windows_tree_stop_uses_job_object_after_root_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A returned root PID must not make Windows cancellation lose its descendants."""

    class FakeProcess:
        pid = 1234
        returncode = 0
        killed = False

        def kill(self) -> None:
            self.killed = True

    class FakeJob:
        terminated = False

        def terminate(self) -> bool:
            self.terminated = True
            return True

    taskkill_calls: list[object] = []

    def taskkill(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        taskkill_calls.append((args, kwargs))
        return subprocess.CompletedProcess([], 1)

    monkeypatch.setattr(process_tree, "is_windows", lambda: True)
    monkeypatch.setattr(subprocess, "run", taskkill)
    process = FakeProcess()
    job = FakeJob()

    process_tree.ProcessTree(
        cast("subprocess.Popen[bytes]", process),
        cast(process_tree.WindowsJobObject, job),
    ).stop(force=False)

    assert job.terminated and not process.killed
    assert taskkill_calls == []


def test_windows_tree_stop_kills_the_root_when_taskkill_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a Job Object, a failed taskkill still leaves no live root behind."""

    class FakeProcess:
        pid = 1234
        killed = False

        def kill(self) -> None:
            self.killed = True

    taskkill_calls: list[object] = []

    def taskkill(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        taskkill_calls.append((args, kwargs))
        return subprocess.CompletedProcess([], 1)

    monkeypatch.setattr(process_tree, "is_windows", lambda: True)
    monkeypatch.setattr(subprocess, "run", taskkill)
    process = FakeProcess()

    process_tree.ProcessTree(cast("subprocess.Popen[bytes]", process), None).stop(
        force=True
    )

    assert len(taskkill_calls) == 1 and process.killed


@pytest.mark.parametrize("state", ["active", "completed", "unavailable"])
def test_worktree_protection_reads_the_runtime_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    tree = _real_tree(tmp_path)
    root = tmp_path / ".harness"
    ledger = root / "orchestration/state"
    ledger.mkdir(parents=True)
    (ledger / "ledger.json").write_text(json.dumps({"version": 4}))

    def call(self: RuntimeClient, operation: str, **kwargs: object) -> RuntimeReply:
        assert operation == "state.read"
        assert kwargs["payload"] == {"collections": ["batches"], "paths": []}
        if state == "unavailable":
            raise RuntimeClientError(
                "runtime_unavailable",
                "offline",
                remedy="start runtime",
                domain="infrastructure",
            )
        return RuntimeReply(
            {},
            {
                "records": {
                    "batches/batch-1.json": {"state": state, "worktree": str(tree)}
                }
            },
            1,
        )

    monkeypatch.setattr(RuntimeClient, "call", call)
    active = cleanup._active_worktrees(root)
    assert active == (
        None if state == "unavailable" else {tree} if state == "active" else set()
    )

    fact = next(item for item in cleanup.worktree_facts(tmp_path) if item.path == tree)
    assert fact.removable == (state == "completed")
