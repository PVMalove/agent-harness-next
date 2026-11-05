"""The screen snapshot requests round-trip through the FastAPI application: the real /ws route
and its security middleware, driven in process over ASGI with fake screen facts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.request_router import RequestRouter
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel.batch_history import History
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult
from harness.console.kernel.reports import ledger_from_payload, timeline_from_payload

from ._asgi_ws import AsgiWebSocket, Rejected
from ._screen_facts import BODY, Facts, service

PORT = 48123
TOKEN = "t" * 43


class Runtime:
    """The server facts the transport reads; its router is the composition's."""

    port = PORT
    token = TOKEN
    closing = False

    def __init__(self, router: RequestRouter, static_root: Path) -> None:
        self.router = router
        self.static_root = static_root
        self.clients = 0

    def client_opened(self) -> None:
        self.clients += 1

    def client_closed(self) -> None:
        self.clients -= 1


def _runtime(tmp_path: Path, facts: Facts) -> Runtime:
    parts = composition.compose(
        tmp_path,
        snapshots=cast(SnapshotService, object()),
        jobs=cast(JobService, object()),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=service(facts),
    )
    return Runtime(parts.router, tmp_path / "no-build")


async def _read(socket: AsgiWebSocket, request: dict[str, object]) -> object:
    await socket.send_text(json.dumps({"id": 1, **request}))
    reply = json.loads(await socket.receive_text())
    assert reply["ok"] is True, reply
    text, snapshot_id = reply["text"], reply["snapshot_id"]
    page = 2
    while not reply["done"]:
        await socket.send_text(
            json.dumps(
                {
                    "id": page,
                    "type": "snapshot.page",
                    "snapshot_id": snapshot_id,
                    "offset": reply["next"],
                }
            )
        )
        reply = json.loads(await socket.receive_text())
        assert reply["ok"] is True and reply["id"] == page, reply
        text += reply["text"]
        page += 1
    return json.loads(text)


def test_every_screen_request_round_trips_through_the_websocket_route(
    tmp_path: Path,
) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            assert runtime.clients == 1
            view = ledger_from_payload(await _read(socket, {"type": "reports.snapshot"}))
            assert view.reports[0].dispatch_id == "d-1"
            body = await _read(socket, {"type": "reports.report", "dispatch_id": "d-1"})
            assert body == {"output": BODY}
            timeline = await _read(
                socket, {"type": "reports.timeline", "batch_id": "b-1"}
            )
            assert timeline_from_payload(timeline).batch.batch_id == "b-1"
            orchestration = await _read(socket, {"type": "orchestration.snapshot"})
            assert isinstance(orchestration, dict)
            assert orchestration["lock"] == {"lock": {"locked": False}, "error": None}
            recovery = await _read(
                socket, {"type": "recovery.snapshot", "batch": "b-1"}
            )
            assert isinstance(recovery, dict)
            assert History.from_payload(recovery["history"]).find("b-1") is not None
            assert ApiResult.from_payload(recovery["status"]).ok
            route = await _read(
                socket, {"type": "container_route.snapshot", "batch": "b-1"}
            )
            assert isinstance(route, dict)
            assert Authored.from_payload(route["authored"]).document == {"roles": {}}
            assert facts.preflights == [("b-1", "developer", "")]
            await socket.send_text(json.dumps({"id": "l", "type": "orchestration.lock"}))
            lock = json.loads(await socket.receive_text())
            assert lock == {
                "v": 1,
                "id": "l",
                "type": "orchestration.lock",
                "ok": True,
                "lock": {"locked": False},
                "error": None,
            }
            await socket.send_text(
                json.dumps({"id": 9, "type": "reports.report", "dispatch_id": "d-9"})
            )
            missing = json.loads(await socket.receive_text())
            assert missing["error"]["code"] == "not_found" and missing["id"] == 9
        assert runtime.clients == 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", f"127.0.0.1:{PORT}".encode())],
        [
            (b"host", f"127.0.0.1:{PORT}".encode()),
            (b"authorization", b"Bearer wrong"),
        ],
        [(b"host", b"evil.example"), (b"authorization", f"Bearer {TOKEN}".encode())],
    ],
    ids=["no-token", "wrong-token", "foreign-host"],
)
def test_the_security_middleware_refuses_a_screen_client_without_the_session(
    tmp_path: Path, headers: list[tuple[bytes, bytes]]
) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def scenario() -> None:
        with pytest.raises(Rejected) as refused:
            async with AsgiWebSocket(
                create_app(runtime), PORT, TOKEN, headers=headers
            ):
                pass
        assert refused.value.status in (401, 403)

    asyncio.run(scenario())
    assert facts.calls == {} and runtime.clients == 0
