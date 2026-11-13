"""The run log of a supervised worker: ``dispatch observe`` and ``dispatch logs`` read the stdout
the runtime keeps of the execution while the worker runs, without asking the runtime for the path.

The seam tests run the coordinator CLI as its own process against the real ``harness-runtime`` and
its fake foreground adapter; the stream-json lines stand in for what a worker prints to the stdout
the runtime redirected into the run log."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from harness.orchestration.ledger.lifecycle import POINTER_NAME, STORE_LEDGER_VERSION
from harness.orchestration.worker_observation import supervised_log_path
from harness.orchestration.workflow import worker_logs
from harness.orchestration.workflow.delivery import execution_operation_id
from tests.orchestration.runtime_store_support import (
    Supervised,
    coordinator_popen,
)

linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="the runtime supervises processes on Linux",
)

INIT = {"type": "system", "subtype": "init", "model": "sonnet"}


def _say(text: str) -> JsonObject:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _append(path: Path, *records: JsonObject) -> None:
    with path.open("a", encoding="utf-8") as log:
        log.write("".join(json.dumps(record) + "\n" for record in records))


def _texts(events: object) -> list[str]:
    assert isinstance(events, list), events
    return [str(event["text"]) for event in events]


def test_the_run_log_path_is_computed_from_the_brief_without_the_runtime(
    tmp_path: Path,
) -> None:
    dispatch: JsonObject = {
        "dispatch_id": "dispatch-a",
        "execution": {"supervisor": "harness-runtime"},
    }

    path, reason = supervised_log_path(tmp_path, dispatch)

    expected = tmp_path / "executions" / execution_operation_id(dispatch) / "stdout.log"
    assert (path, reason) == (expected.resolve(), None)
    assert supervised_log_path(tmp_path, {"dispatch_id": "dispatch-a"}) == (
        None,
        "no_log",
    )


@pytest.fixture
def supervised(tmp_path: Path) -> Iterator[Supervised]:
    repo = Supervised(tmp_path)
    yield repo
    repo.close()


def _run_log(repo: Supervised) -> Path:
    """The stdout the runtime redirected for the running execution, as the runtime names it."""
    execution = repo.wait_execution("running")
    launch = execution["launch"]
    assert isinstance(launch, dict), execution
    logs = launch["logs"]
    assert isinstance(logs, dict), launch
    return Path(str(logs["stdout"]))


def _answer(result: object) -> JsonObject:
    assert getattr(result, "returncode") == 0, getattr(result, "stderr")
    parsed: JsonObject = json.loads(getattr(result, "stdout"))
    return parsed


@linux_only
def test_observe_and_logs_read_the_run_log_while_the_worker_runs(
    supervised: Supervised,
) -> None:
    repo = supervised
    _answer(repo.send())
    log = _run_log(repo)
    _append(log, INIT, _say("reading the brief"))

    observed = _answer(repo.run("dispatch", "observe", "--dispatch", repo.dispatch))
    page = _answer(repo.run("dispatch", "logs", "--dispatch", repo.dispatch))
    rest = _answer(
        repo.run(
            "dispatch",
            "logs",
            "--dispatch",
            repo.dispatch,
            "--offset",
            str(page["next_offset"]),
        )
    )

    assert _texts(observed["events"]) == [
        "Runtime session connected",
        "reading the brief",
    ]
    assert page["source"] == "execution"
    assert page["execution_state"] == "running"
    assert page["stream_state"] == "connected"
    assert _texts(page["events"]) == _texts(observed["events"])
    assert page["next_offset"] == log.stat().st_size
    assert rest["events"] == [] and rest["next_offset"] == page["next_offset"]


@linux_only
def test_logs_follow_prints_new_events_and_ends_after_the_worker_exits(
    supervised: Supervised,
) -> None:
    repo = supervised
    _answer(repo.send())
    log = _run_log(repo)
    _append(log, INIT)
    follow = coordinator_popen(
        repo.repo,
        repo.runtime,
        "dispatch",
        "logs",
        "--dispatch",
        repo.dispatch,
        "--follow",
        "--poll-seconds",
        "0.1",
    )
    try:
        time.sleep(0.5)
        _append(log, _say("half way"))
        time.sleep(0.5)
        repo.release(0)
        stdout, stderr = follow.communicate(timeout=60)
    finally:
        with contextlib.suppress(OSError):
            follow.kill()

    assert follow.returncode == 0, stderr
    lines = [json.loads(line) for line in stdout.splitlines()]
    *events, summary = lines
    assert _texts(events) == ["Runtime session connected", "half way"]
    assert summary["execution_state"] == "exited"
    assert summary["source"] == "execution"
    assert summary["next_offset"] == log.stat().st_size


class _ExclusiveLock:
    """A ledger lock that another command holds after the first, short read."""

    def __init__(self) -> None:
        self.entered = 0

    @contextlib.contextmanager
    def __call__(self, _ledger: object) -> Iterator[None]:
        self.entered += 1
        if self.entered > 1:
            raise AssertionError(
                "dispatch logs took the ledger lock in its follow loop"
            )
        yield


def _store_dispatch(tmp_path: Path) -> tuple[Path, JsonObject]:
    root = tmp_path / ".harness/orchestration/state"
    root.mkdir(parents=True)
    (root / POINTER_NAME).write_text(
        json.dumps({"version": STORE_LEDGER_VERSION}), encoding="utf-8"
    )
    dispatch: JsonObject = {
        "dispatch_id": "dispatch-a",
        "resolved_transport": "external",
        "execution": {"supervisor": "harness-runtime"},
    }
    path = root / "executions" / execution_operation_id(dispatch) / "stdout.log"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    return path, dispatch


def _follow_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        repo=str(tmp_path),
        state_dir=None,
        dispatch="dispatch-a",
        offset=0,
        follow=True,
        poll_seconds=0.0,
    )


def test_follow_reads_the_records_once_and_polls_without_the_ledger_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log, dispatch = _store_dispatch(tmp_path)
    lock = _ExclusiveLock()
    monkeypatch.setattr(worker_logs, "_ledger_lock", lock)
    monkeypatch.setattr(worker_logs, "_load_dispatch", lambda _root, _id: dispatch)
    monkeypatch.setattr(
        worker_logs, "_load_dispatch_status", lambda _root, _id: {"state": "working"}
    )
    states = iter(["running", "running", "running", "exited"])

    def observe(_repo: Path, _dispatch_id: str) -> JsonObject:
        state = next(states, "exited")
        if state == "running":
            _append(log, _say(f"poll {log.stat().st_size}"))
        return {"state": state}

    monkeypatch.setattr(worker_logs, "observed_execution", observe)

    summary = worker_logs.dispatch_logs(_follow_args(tmp_path))

    printed = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lock.entered == 1
    assert len(printed) == 3
    assert all(event["kind"] == "output" for event in printed)
    assert summary["execution_state"] == "exited"
    assert summary["state"] == "working"
    assert summary["next_offset"] == log.stat().st_size


def test_an_interrupted_follow_exits_130_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _log, dispatch = _store_dispatch(tmp_path)
    monkeypatch.setattr(worker_logs, "_load_dispatch", lambda _root, _id: dispatch)
    monkeypatch.setattr(
        worker_logs, "_load_dispatch_status", lambda _root, _id: {"state": "working"}
    )

    def interrupted(_repo: Path, _dispatch_id: str) -> JsonObject:
        raise KeyboardInterrupt

    monkeypatch.setattr(worker_logs, "observed_execution", interrupted)

    with pytest.raises(SystemExit) as stopped:
        worker_logs.dispatch_logs(_follow_args(tmp_path))

    assert stopped.value.code == 130
