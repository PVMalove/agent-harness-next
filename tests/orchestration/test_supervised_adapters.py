"""The shipped adapters under the real ``harness-runtime`` supervisor: the adapter lives as long as
its worker, so the runtime sees the worker's lifetime, exit code and stop (#1124, ADR 0022).

The adapters are the real ``harness/adapters/*.py``; only the ``claude`` and ``codex app-server``
binaries are fakes (``runtime_store_support.FAKE_WORKER``)."""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest

from harness.orchestration.ledger.lifecycle import JsonObject
from tests.orchestration.fake_clock import FakeClock
from tests.orchestration.runtime_store_support import Supervised, architect_report_file
from tests.orchestration.test_runtime_supervisor import (
    DEADLINE,
    GRACE,
    alive,
    dig,
    past,
    sent,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the runtime supervises processes on Linux",
)


class Factory(Protocol):
    def __call__(self, *, clock: bool = ...) -> Supervised: ...


@pytest.fixture
def supervised(tmp_path: Path) -> Iterator[Factory]:
    made: list[Supervised] = []

    def make(*, clock: bool = False) -> Supervised:
        tmp = tmp_path / f"s{len(made)}"
        tmp.mkdir()
        repo = Supervised(
            tmp,
            timeout=DEADLINE if clock else 600,
            grace=GRACE if clock else 1,
            clock=FakeClock(tmp) if clock else None,
        )
        made.append(repo)
        return repo

    yield make
    for repo in made:
        repo.close()


def wait_for(repo: Supervised, event: str, timeout: float = 60.0) -> JsonObject:
    """The first ``event`` the fake worker logged."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for entry in repo.worker_log():
            if entry["event"] == event:
                return entry
        time.sleep(0.05)
    pytest.fail(f"the fake worker logged no {event!r}: {repo.worker_log()}")


def settled(repo: Supervised) -> JsonObject:
    """The dispatch status after the execution exited and ``dispatch status`` reacted to it."""
    execution = repo.wait_execution("exited", timeout=60)
    answer = repo.run("dispatch", "status", "--dispatch", repo.dispatch)
    assert answer.returncode == 0, answer.stderr
    status = repo.status()
    status["execution"] = execution
    return status


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_a_worker_that_reports_after_five_seconds_is_reported_and_never_blocked(
    supervised: Factory, runtime: str
) -> None:
    repo = supervised()
    report = architect_report_file(repo.repo, repo.dispatch, repo.brief)
    repo.use_adapter(runtime, delay=5, report=str(report))

    sent(repo.send())
    started = wait_for(repo, "started")
    receipt_pid = dig(repo.execution(), "identity", "pid")
    # The worker runs in the group the runtime made the adapter lead.
    assert started["pgid"] == receipt_pid

    status = settled(repo)

    answers = {entry["event"]: entry for entry in repo.worker_log() if "code" in entry}
    for step in ("dispatch self-report", "dispatch heartbeat", "report submit"):
        assert answers[step]["code"] == 0, answers[step]
    assert status["state"] == "reported", status
    assert dig(status["execution"], "exit", "exit_code") == 0
    if runtime == "claude":
        call = wait_for(repo, "claude")
        argv = call["argv"]
        assert isinstance(argv, list) and isinstance(argv[1], str)
        # The prompt is the argument right after -p; the worker's stdin is empty.
        assert argv[0] == "-p"
        assert "dispatch self-report" in argv[1]
        assert call["stdin"] == ""


def test_a_worker_exit_code_is_the_execution_exit_code_and_the_runtime_failure_code(
    supervised: Factory,
) -> None:
    repo = supervised()
    repo.use_adapter("claude", exit_code=7)

    sent(repo.send())
    status = settled(repo)

    assert dig(status["execution"], "exit", "exit_code") == 7
    assert status["state"] == "blocked"
    assert dig(status, "runtime_failure", "kind") == "worker-exited-without-report"
    assert dig(status, "runtime_failure", "exit_code") == 7


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_a_runtime_stop_of_the_execution_also_ends_the_worker(
    supervised: Factory, runtime: str
) -> None:
    repo = supervised(clock=True)
    repo.use_adapter(runtime, hang=True)
    sent(repo.send())
    worker = wait_for(repo, "started")["pid"]
    assert isinstance(worker, int)

    past(repo, DEADLINE + 1)
    exited = repo.wait_execution("exited", timeout=60)

    assert dig(exited, "exit", "stopped_by") == "deadline"
    assert not alive(worker)
