"""The coordinator commands of the Recovery and Container route screens over a fake console
server client: reads map to screen snapshots, recovery actions to server jobs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from harness.console.kernel.batch_history import History, HistoryBatch, load_history
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, ArgvError, Outcome
from harness.console.tui.client import (
    ConnectionLost,
    JobResult,
    RecoveryFacts,
    RouteFacts,
    ServerError,
)
from harness.console.tui.server_api import ServerCoordinatorApi

REPO = Path("/work/project")
STATUS = ApiResult(Outcome.DOCUMENT, ("status",), ({"batch_id": "b-1"},), 0)
PREFLIGHT = ApiResult(Outcome.REFUSED, ("preflight",), ({"verified": False},), 2)


class FakeClient:
    """The screen client methods the server API uses, recording every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.job = JobResult("completed", 0, json.dumps({"ok": True}), "", False, None)
        self.failure: Exception | None = None

    def _maybe_fail(self) -> None:
        if self.failure is not None:
            raise self.failure

    def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> RecoveryFacts:
        self.calls.append(("recovery", batch, tuple(skip)))
        self._maybe_fail()
        history = History(
            (HistoryBatch("b-1", "#1", "br", "active", "t", False, 2, 1, "qa"),)
        )
        return RecoveryFacts(history, STATUS if batch else None)

    def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> RouteFacts:
        self.calls.append(("route", batch, role, runtime))
        self._maybe_fail()
        return RouteFacts(Authored({}), PREFLIGHT if batch else None)

    def run_job(
        self, command_id: str, values: Mapping[str, str], *, confirmed: bool = False
    ) -> JobResult:
        self.calls.append(("job", command_id, dict(values), confirmed))
        self._maybe_fail()
        return self.job


class NoRunner:
    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("a server-backed call must never start a process")


def _api(client: FakeClient) -> ServerCoordinatorApi:
    return ServerCoordinatorApi(REPO, client)  # type: ignore[arg-type]


def test_the_batch_list_is_the_recovery_history_and_loads_as_the_same_history() -> None:
    client = FakeClient()
    history = load_history(_api(client))
    assert history.batches[0].batch_id == "b-1" and history.batches[0].open_dispatches == 1
    assert client.calls == [("recovery", "", ())]


def test_status_and_preflight_are_screen_snapshot_reads() -> None:
    client = FakeClient()
    api = _api(client)
    status = api.call(("recovery", "status"), {"batch": "b-1", "json": True, "skip": ["x"]})
    assert status == STATUS
    preflight = api.call(
        ("dispatch", "preflight"), {"batch": "b-1", "role": "qa", "runtime": "r"}
    )
    assert preflight == PREFLIGHT
    assert client.calls == [("recovery", "b-1", ("x",)), ("route", "b-1", "qa", "r")]


@pytest.mark.parametrize(
    ("path", "values", "command_id", "flat"),
    [
        (("recovery", "reload"), {"batch": "b", "json": True}, "recovery-reload", {"batch": "b", "json": "1"}),
        (("recovery", "abort"), {"batch": "b", "json": True}, "recovery-abort", {"batch": "b", "json": "1"}),
        (("recovery", "fix"), {"batch": "b", "json": True}, "recovery-fix", {"batch": "b", "json": "1"}),
        (
            ("recovery", "fix"),
            {"batch": "b", "json": True, "apply": True},
            "recovery-fix-apply",
            {"batch": "b", "json": "1"},
        ),
        (
            ("recovery", "resume"),
            {"batch": "b", "json": True, "approved_by": "dev", "note": ""},
            "recovery-resume",
            {"batch": "b", "json": "1", "approved_by": "dev", "note": ""},
        ),
    ],
)
def test_recovery_actions_are_server_jobs_and_forward_confirmed_only_when_given(
    path: tuple[str, ...], values: dict[str, object], command_id: str, flat: dict[str, str]
) -> None:
    client = FakeClient()
    api = _api(client)
    result = api.call(path, values)  # type: ignore[arg-type]
    assert result.ok and result.document == {"ok": True}
    assert result.argv[4 : 4 + len(path)] == path
    api.call(path, values, confirmed=True)  # type: ignore[arg-type]
    assert client.calls == [
        ("job", command_id, flat, False),
        ("job", command_id, flat, True),
    ]
    assert ("--apply" in result.argv) is (command_id == "recovery-fix-apply")


def test_a_job_refusal_or_a_lost_connection_is_unavailable_never_raised() -> None:
    client = FakeClient()
    client.failure = ServerError("confirmation_required", "confirm first")
    refused = _api(client).call(("recovery", "resume"), {"batch": "b"})
    assert refused.outcome is Outcome.UNAVAILABLE and "confirmation_required" in refused.stderr
    client.failure = ConnectionLost("gone")
    lost = _api(client).call(("recovery", "status"), {"batch": "b", "json": True})
    assert lost.outcome is Outcome.UNAVAILABLE and lost.stderr == "gone"


def test_a_job_that_failed_without_an_exit_code_is_unavailable() -> None:
    client = FakeClient()
    client.job = JobResult("failed", None, "", "", False, "executor failed")
    result = _api(client).call(("recovery", "reload"), {"batch": "b"})
    assert result.outcome is Outcome.UNAVAILABLE and result.stderr == "executor failed"


def test_without_a_fallback_a_path_the_server_does_not_serve_is_refused() -> None:
    api = _api(FakeClient())
    for path, values in (
        (("dispatch", "propose"), {"batch": "b"}),
        (("qa", "run"), {"dispatch": "d"}),
        (("dispatch", "preflight"), {"batch": "b", "role": "qa", "purpose": "work"}),
    ):
        with pytest.raises(ArgvError):
            api.call(path, values)
    with pytest.raises(ArgvError):
        api.cleanup()


def test_with_a_fallback_only_unserved_paths_reach_its_runner() -> None:
    from harness.console.kernel.coordinator_api import CoordinatorApi

    calls: list[list[str]] = []

    def runner(argv: Sequence[str], **kwargs: object) -> object:
        import subprocess

        calls.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, "{}", "")

    client = FakeClient()
    api = ServerCoordinatorApi(
        REPO, client, fallback=CoordinatorApi(REPO, runner)  # type: ignore[arg-type]
    )
    assert api.call(("recovery", "reload"), {"batch": "b"}).ok
    assert api.call(("dispatch", "status")).ok
    assert len(calls) == 1 and calls[0][-2:] == ["dispatch", "status"]
