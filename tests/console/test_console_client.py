"""The console WebSocket client against a real console server on loopback, and against a tiny
server that answers with what a console server never sends."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest

from harness.console.kernel.discovery import ServerEndpoint
from harness.console.kernel.home_snapshot import (
    HomeContext,
    build_home_snapshot,
)
from harness.console.kernel import reports
from harness.console.tui.client import (
    ConnectionLost,
    ConsoleClient,
    LockUnavailable,
    MalformedReply,
    ServerError,
    WorkerSteps,
)
from tests.console.test_snapshots import DATA, MEMORY, VIEW

SNAPSHOT = build_home_snapshot(DATA, HomeContext(repo_map=VIEW, memory=MEMORY))


class _Loop:
    """An event loop on a thread of its own: the client under test is synchronous."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def run[T](self, coroutine: Awaitable[T]) -> T:
        async def wrapped() -> T:
            return await coroutine

        return asyncio.run_coroutine_threadsafe(wrapped(), self.loop).result(10)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(5)
        self.loop.close()


















Answer = Callable[[dict[str, object]], str | bytes | list[str]]


@contextmanager
def _fake_server(answer: Answer) -> Iterator[ServerEndpoint]:
    """A WebSocket server that answers every request with `answer(request)`."""
    from websockets.asyncio.server import ServerConnection, serve

    async def handler(connection: ServerConnection) -> None:
        async for raw in connection:
            replies = answer(json.loads(raw))
            for reply in replies if isinstance(replies, list) else [replies]:
                await connection.send(reply)

    loop = _Loop()

    async def start() -> object:
        return await serve(handler, "127.0.0.1", 0, compression=None)

    server = loop.run(start())
    port = server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    try:
        yield ServerEndpoint(port, "token")
    finally:
        server.close()  # type: ignore[attr-defined]
        loop.run(server.wait_closed())  # type: ignore[attr-defined]
        loop.stop()


def _reply(request: dict[str, object], **changes: object) -> str:
    reply: dict[str, object] = {
        "v": 1,
        "id": request["id"],
        "type": request["type"],
        "ok": True,
        "cached": False,
        "age_seconds": 0.0,
        "snapshot": json.loads(json.dumps(SNAPSHOT.to_payload())),
    }
    reply.update(changes)
    return json.dumps(reply)


@pytest.mark.parametrize(
    "answer",
    [
        lambda request: "not json",
        lambda request: b"\x00binary",
        lambda request: "[]",
        lambda request: _reply(request, v=2),
        lambda request: _reply(request, id="someone-else"),
        lambda request: _reply(request, type="decisions.snapshot"),
        lambda request: _reply(request, ok="yes"),
        lambda request: _reply(request, snapshot={"version": 1}),
        lambda request: _reply(request, ok=False, error="bad"),
    ],
    ids=[
        "not-json",
        "binary",
        "not-object",
        "version",
        "foreign-id",
        "foreign-type",
        "ok-not-bool",
        "bad-snapshot",
        "bad-error",
    ],
)
def test_a_reply_outside_the_protocol_is_malformed(answer: Answer) -> None:
    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(MalformedReply):
                client.home()
        finally:
            client.close()


def test_a_server_that_closes_mid_request_is_connection_lost() -> None:
    """The real server cannot be closed under an unfinished request: its listener waits for the
    connection. A server that drops the connection instead of answering stands in for it."""
    from websockets.asyncio.server import ServerConnection, serve

    async def dropping(connection: ServerConnection) -> None:
        await connection.recv()
        await connection.close(1011, "going away")

    loop = _Loop()

    async def start() -> object:
        return await serve(dropping, "127.0.0.1", 0, compression=None)

    server = loop.run(start())
    port = server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    try:
        client = ConsoleClient.connect(ServerEndpoint(port, "token"))
        with pytest.raises(ConnectionLost):
            client.home()
        with pytest.raises(ConnectionLost):
            client.home()
        client.close()
    finally:
        server.close()  # type: ignore[attr-defined]
        loop.run(server.wait_closed())  # type: ignore[attr-defined]
        loop.stop()


_PAGED = build_home_snapshot(
    replace(DATA, problems=(("fail", "a.b", "x" * 400),)), HomeContext()
)


def _paged(**page: object) -> Callable[[dict[str, object]], str]:
    """A server whose Home reply names a problem page and whose page reply is `page`."""

    def answer(request: dict[str, object]) -> str:
        if request["type"] == "home.snapshot":
            reply = json.loads(_reply(request, problems_snapshot_id=7))
            reply["snapshot"] = json.loads(json.dumps(_PAGED.to_payload()))
            return json.dumps(reply)
        assert (request["snapshot_id"], request["offset"]) == (7, 0)
        body = {"v": 1, "id": request["id"], "type": request["type"], "ok": True}
        return json.dumps({**body, **page})

    return answer


@pytest.mark.parametrize(
    "answer",
    [
        lambda request: _reply(request, problems_snapshot_id="7"),
        lambda request: _reply(request, problems_snapshot_id=True),
        _paged(text="[]", next=2),
        _paged(text="[", next=0, done=False),
        _paged(text=1, next=1, done=True),
        _paged(text="[]", next=True, done=True),
        _paged(text="not json", next=8, done=True),
        _paged(text='[{"status": "fail"}]', next=20, done=True),
        _paged(text="[]", next=2, done=True),
    ],
    ids=[
        "page-id-string",
        "page-id-bool",
        "page-without-done",
        "page-that-does-not-move-on",
        "page-text-not-string",
        "page-next-bool",
        "problems-not-json",
        "problem-outside-schema",
        "fewer-problems-than-total",
    ],
)
def test_a_problem_page_outside_the_protocol_is_malformed(answer: Answer) -> None:
    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(MalformedReply):
                client.home()
        finally:
            client.close()


def test_an_expired_problem_page_is_a_server_error() -> None:
    def answer(request: dict[str, object]) -> str | bytes:
        if request["type"] == "home.snapshot":
            return _paged()(request)
        return json.dumps(
            {
                "v": 1,
                "id": request["id"],
                "type": request["type"],
                "ok": False,
                "error": {"code": "snapshot_expired", "message": "again"},
            }
        )

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(ServerError) as failed:
                client.home()
        finally:
            client.close()
    assert failed.value.code == "snapshot_expired"


def test_the_well_formed_fake_reply_is_accepted() -> None:
    with _fake_server(_reply) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            assert client.home() == SNAPSHOT
        finally:
            client.close()




def test_no_reply_within_the_reply_timeout_is_connection_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from websockets.asyncio.server import ServerConnection, serve

    from harness.console.tui import client as console_client

    monkeypatch.setattr(console_client, "REPLY_TIMEOUT", 0.3)

    async def silent(connection: ServerConnection) -> None:
        async for _raw in connection:
            pass

    loop = _Loop()

    async def start() -> object:
        return await serve(silent, "127.0.0.1", 0, compression=None)

    server = loop.run(start())
    port = server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]
    try:
        client = ConsoleClient.connect(ServerEndpoint(port, "token"))
        with pytest.raises(ConnectionLost):
            client.home()
        with pytest.raises(ConnectionLost):
            client.home()
        client.close()
    finally:
        server.close()  # type: ignore[attr-defined]
        loop.run(server.wait_closed())  # type: ignore[attr-defined]
        loop.stop()


def _ok(request: dict[str, object], **fields: object) -> str:
    return json.dumps(
        {"v": 1, "id": request["id"], "type": request["type"], "ok": True, **fields}
    )


def _failed(request: dict[str, object], code: str) -> str:
    return json.dumps(
        {
            "v": 1,
            "id": request["id"],
            "type": request["type"],
            "ok": False,
            "error": {"code": code, "message": code},
        }
    )


def _pages(text: str, size: int) -> Callable[[dict[str, object]], str]:
    """A server that hands `text` out in pages of `size` characters under snapshot id 5."""

    def answer(request: dict[str, object]) -> str:
        offset = request.get("offset", 0)
        assert isinstance(offset, int)
        if request["type"] == "snapshot.page":
            assert request["snapshot_id"] == 5
        end = min(offset + size, len(text))
        return _ok(
            request, snapshot_id=5, text=text[offset:end], next=end, done=end == len(text)
        )

    return answer


def _ledger_text() -> str:
    view = reports.LedgerView(
        batches=[reports.BatchSummary("b-1", "#1", "active", "t" * 300)]
    )
    return json.dumps(reports.ledger_payload(view))


def test_a_snapshot_is_read_across_several_pages_and_parsed_once() -> None:
    requests: list[dict[str, object]] = []
    pages = _pages(_ledger_text(), 50)

    def answer(request: dict[str, object]) -> str:
        requests.append(request)
        return pages(request)

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            view = client.reports(online=True)
        finally:
            client.close()
    assert view.batches[0].batch_id == "b-1"
    assert requests[0] == {"id": 1, "type": "reports.snapshot", "force": False, "online": True}
    assert len(requests) > 3
    assert all(item["type"] == "snapshot.page" for item in requests[1:])


@pytest.mark.parametrize(
    "answer",
    [
        lambda request: _ok(request, snapshot_id=5, text="{", next=0, done=False),
        lambda request: _ok(request, snapshot_id="5", text="{}", next=2, done=True),
        lambda request: _ok(request, snapshot_id=5, text="[]", next=2, done=True),
        lambda request: _ok(request, snapshot_id=5, text="{]", next=2, done=True),
        lambda request: _ok(request, snapshot_id=5, text="{}", next=2),
    ],
    ids=["page-does-not-move-on", "id-string", "not-object", "not-json", "no-done"],
)
def test_a_malformed_snapshot_page_is_refused(answer: Answer) -> None:
    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(MalformedReply):
                client.orchestration()
        finally:
            client.close()


def test_an_unknown_report_or_batch_is_none_and_other_errors_raise() -> None:
    def answer(request: dict[str, object]) -> str:
        if request["type"] == "reports.timeline" and request["batch_id"] == "b-2":
            return _failed(request, "collect_failed")
        return _failed(request, "not_found")

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            assert client.report("d-9") is None
            assert client.timeline("b-9") is None
            with pytest.raises(ServerError):
                client.timeline("b-2")
        finally:
            client.close()


def test_the_ledger_lock_poll_and_its_unavailable_reason() -> None:
    answers: Iterator[dict[str, object]] = iter(
        [{"lock": {"locked": False}, "error": None}, {"lock": None, "error": "занят"}]
    )

    def answer(request: dict[str, object]) -> str:
        return _ok(request, **next(answers))

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            assert client.ledger_lock() == {"locked": False}
            with pytest.raises(LockUnavailable, match="занят"):
                client.ledger_lock()
        finally:
            client.close()


def _job(phase: str, cursor: int, output: list[dict[str, str]], **rest: object) -> dict[str, object]:
    return {
        "id": "job-1",
        "command_id": "recovery-reload",
        "phase": phase,
        "cursor": cursor,
        "done": phase != "running",
        "truncated": False,
        "returncode": rest.get("returncode"),
        "error": None,
        "output": output,
    }


def test_a_job_is_started_and_followed_until_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.console.tui import client as console_client

    monkeypatch.setattr(console_client, "JOB_POLL_SECONDS", 0.01)
    requests: list[dict[str, object]] = []

    def answer(request: dict[str, object]) -> str | list[str]:
        requests.append(request)
        if request["type"] == "job.start":
            return _ok(
                request, job=_job("running", 1, [{"channel": "stdout", "text": '{"a"'}])
            )
        if request["cursor"] == 1:
            return _ok(request, job=_job("running", 2, [{"channel": "stderr", "text": "w"}]))
        return _ok(
            request,
            job=_job("completed", 3, [{"channel": "stdout", "text": ": 1}"}], returncode=0),
        )

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            result = client.run_job("recovery-reload", {"batch": "b-1"})
        finally:
            client.close()
    assert result.phase == "completed" and result.returncode == 0
    assert (result.stdout, result.stderr) == ('{"a": 1}', "w")
    assert requests[0] == {
        "id": 1,
        "type": "job.start",
        "command_id": "recovery-reload",
        "values": {"batch": "b-1"},
        "confirmed": False,
        "client": "tui",
    }
    assert requests[1:] == [
        {"id": 2, "type": "job.get", "job_id": "job-1", "cursor": 1},
        {"id": 3, "type": "job.get", "job_id": "job-1", "cursor": 2},
    ]


def test_a_quiet_running_job_neither_blocks_other_requests_nor_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from harness.console.tui import client as console_client

    monkeypatch.setattr(console_client, "REPLY_TIMEOUT", 0.3)
    monkeypatch.setattr(console_client, "JOB_POLL_SECONDS", 0.01)
    following, finish = threading.Event(), threading.Event()

    def answer(request: dict[str, object]) -> str | list[str]:
        if request["type"] in {"job.get", "job.subscribe"}:
            following.set()
        if request["type"] == "orchestration.lock":
            return _ok(request, lock={"locked": False}, error=None)
        if request["type"] == "job.subscribe":
            return []  # a quiet job: nothing to stream yet
        if request["type"] == "job.get" and finish.is_set():
            return _ok(request, job=_job("completed", 1, [], returncode=0))
        return _ok(request, job=_job("running", 1, []))

    results: list[object] = []
    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            job = threading.Thread(
                target=lambda: results.append(client.run_job("recovery-reload", {}))
            )
            job.start()
            assert following.wait(5)
            assert client.ledger_lock() == {"locked": False}
            threading.Event().wait(0.6)
            assert job.is_alive()
            finish.set()
            job.join(5)
        finally:
            client.close()
    assert [getattr(result, "phase", result) for result in results] == ["completed"]


def test_a_refused_job_start_surfaces_its_code() -> None:
    with _fake_server(lambda request: _failed(request, "confirmation_required")) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(ServerError) as refused:
                client.run_job("recovery-fix-apply", {"batch": "b"})
        finally:
            client.close()
    assert refused.value.code == "confirmation_required"


def _steps_page(**changes: object) -> dict[str, object]:
    page: dict[str, object] = {
        "dispatch_id": "dispatch-a",
        "source": "plain",
        "structure": "unavailable",
        "state": "connected",
        "reason": None,
        "message": "",
        "offset": 42,
        "reset": False,
        "more": False,
        "last_step_age_seconds": 3,
        "steps": [{"kind": "log", "text": "working"}],
    }
    page.update(changes)
    return page


def test_worker_steps_are_read_by_offset_with_their_structure_and_state() -> None:
    requests: list[dict[str, object]] = []
    pages = iter(
        [
            _steps_page(),
            _steps_page(
                state="unavailable", reason="log_missing", message="gone", steps=[]
            ),
        ]
    )

    def answer(request: dict[str, object]) -> str:
        requests.append(request)
        if request["dispatch_id"] == "dispatch-x":
            return _failed(request, "not_found")
        return _ok(request, page=next(pages))

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            first = client.worker_steps("dispatch-a", 0)
            second = client.worker_steps("dispatch-a", 42)
            missing = client.worker_steps("dispatch-x", 0)
        finally:
            client.close()

    assert first == WorkerSteps(
        source="plain",
        structure="unavailable",
        state="connected",
        reason=None,
        message="",
        offset=42,
        reset=False,
        more=False,
        last_step_age_seconds=3,
        steps=(("log", "working"),),
    )
    assert second is not None and (second.state, second.reason) == (
        "unavailable",
        "log_missing",
    )
    assert missing is None
    assert [(r["type"], r["dispatch_id"], r["offset"]) for r in requests] == [
        ("worker.steps", "dispatch-a", 0),
        ("worker.steps", "dispatch-a", 42),
        ("worker.steps", "dispatch-x", 0),
    ]


@pytest.mark.parametrize(
    "page",
    [
        "not a page",
        _steps_page(structure="maybe"),
        _steps_page(offset=-1),
        _steps_page(offset=True),
        _steps_page(steps=[{"kind": "log"}]),
        _steps_page(steps=[{"kind": "tool", "text": "x", "input": {}}]),
        _steps_page(reason="because"),
    ],
    ids=["not-object", "structure", "negative", "bool", "no-text", "extra", "reason"],
)
def test_a_worker_steps_page_outside_the_protocol_is_malformed(page: object) -> None:
    def answer(request: dict[str, object]) -> str:
        return _ok(request, page=page)

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            with pytest.raises(MalformedReply):
                client.worker_steps("dispatch-a", 0)
        finally:
            client.close()


def test_every_server_step_reason_is_accepted_and_has_screen_text() -> None:
    from harness.console.backend.domain.worker_steps import REASONS
    from harness.console.tui.screens.worker_observation import STEP_REASONS

    def answer(request: dict[str, object]) -> str:
        return _ok(
            request,
            page=_steps_page(
                state="unavailable",
                reason=request["dispatch_id"],
                message="m",
                steps=[],
            ),
        )

    with _fake_server(answer) as endpoint:
        client = ConsoleClient.connect(endpoint)
        try:
            pages = [client.worker_steps(reason, 0) for reason in REASONS]
        finally:
            client.close()

    assert [page.reason if page else None for page in pages] == list(REASONS)
    assert "log_unrecognised" in REASONS
    assert set(REASONS) <= set(STEP_REASONS)
