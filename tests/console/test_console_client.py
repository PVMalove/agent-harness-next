"""The console WebSocket client against a real console server on loopback, and against a tiny
server that answers with what a console server never sends."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import threading
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from harness.console.client import (
    ConnectionLost,
    ConsoleClient,
    ConsoleClientError,
    MalformedReply,
    ServerError,
    ServerUnavailable,
    TokenRejected,
)
from harness.console.kernel.discovery import ServerEndpoint, read_record
from harness.console.backend.server import ConsoleServer
from harness.console.backend.application.snapshots import (
    HomeContext,
    HomeSnapshot,
    SnapshotService,
    build_home_snapshot,
)
from tests.console.test_snapshots import DATA, MEMORY, VIEW, FakeClock

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


@contextmanager
def _server(
    repo: Path,
    collect: Callable[[Path], HomeSnapshot] = lambda repo: SNAPSHOT,
    collect_online: Callable[[Path], HomeSnapshot] | None = None,
) -> Iterator[tuple[ConsoleServer, _Loop]]:
    loop = _Loop()
    service = SnapshotService(
        repo,
        clock=FakeClock(),
        collect=collect,
        collect_online=collect_online or collect,
    )
    server = loop.run(_make_server(repo, service))
    try:
        yield server, loop
    finally:
        loop.run(server.close())
        loop.stop()


async def _make_server(repo: Path, service: SnapshotService) -> ConsoleServer:
    server = ConsoleServer(repo, snapshots=service)
    await server.start()
    return server


def _endpoint(repo: Path) -> ServerEndpoint:
    endpoint = read_record(repo)
    assert endpoint is not None
    return endpoint


def test_home_returns_the_server_snapshot_and_forwards_force_and_online(
    project: Path,
) -> None:
    online = build_home_snapshot(DATA, HomeContext())
    with _server(project, collect_online=lambda repo: online):
        client = ConsoleClient.connect(_endpoint(project))
        try:
            assert client.home() == SNAPSHOT
            assert client.home(force=True) == SNAPSHOT
            assert client.home(online=True) == online
        finally:
            client.close()


def test_a_missing_record_or_closed_port_is_server_unavailable(project: Path) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(ServerUnavailable):
        ConsoleClient.connect(ServerEndpoint(port, "secret-token"), open_timeout=2)


def test_a_wrong_token_is_token_rejected_and_never_named(project: Path) -> None:
    with _server(project):
        endpoint = _endpoint(project)
        with pytest.raises(TokenRejected) as rejected:
            ConsoleClient.connect(ServerEndpoint(endpoint.port, "wrong-token-value"))
    assert "wrong-token-value" not in str(rejected.value)
    assert isinstance(rejected.value, ConsoleClientError)


def test_a_failed_collect_is_a_server_error_with_its_code(project: Path) -> None:
    def boom(repo: Path) -> HomeSnapshot:
        raise OSError("/private/path")

    with _server(project, collect=boom):
        client = ConsoleClient.connect(_endpoint(project))
        try:
            with pytest.raises(ServerError) as failed:
                client.home()
        finally:
            client.close()
    assert (failed.value.code, failed.value.message) == ("collect_failed", "OSError")


def test_home_reads_every_problem_whole_beyond_one_reply(project: Path) -> None:
    """What one reply lists is capped; the client pages the rest, so the snapshot it returns is
    the one the server built, problem for problem."""
    from tests.console.test_snapshots import _many_problems

    many = build_home_snapshot(_many_problems(400, "сообщение " * 60), HomeContext())
    online = build_home_snapshot(_many_problems(130, "x" * 1000), HomeContext())
    with _server(
        project, collect=lambda repo: many, collect_online=lambda repo: online
    ):
        client = ConsoleClient.connect(_endpoint(project))
        try:
            assert client.home() == many
            assert client.home(online=True) == online
        finally:
            client.close()


Answer = Callable[[dict[str, object]], str | bytes]


@contextmanager
def _fake_server(answer: Answer) -> Iterator[ServerEndpoint]:
    """A WebSocket server that answers every request with `answer(request)`."""
    from websockets.asyncio.server import ServerConnection, serve

    async def handler(connection: ServerConnection) -> None:
        async for raw in connection:
            await connection.send(answer(json.loads(raw)))

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


def _paged(**page: object) -> Answer:
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


def test_client_imports_without_transport_dependencies() -> None:
    code = """
import importlib.abc, json, sys
class Absent(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'h11', 'websockets'}:
            raise ModuleNotFoundError(fullname)
sys.meta_path.insert(0, Absent())
import harness.console.client
print(json.dumps({'loaded': sorted(set(sys.modules) & {'h11', 'websockets'})}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"loaded": []}


def test_no_reply_within_the_reply_timeout_is_connection_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from websockets.asyncio.server import ServerConnection, serve

    from harness.console import client as console_client

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
