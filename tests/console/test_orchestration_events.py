"""Live orchestration events are tested on real loopback sockets over a fixture project: the
ledger records are written by the real `LifecycleLedger`, as the coordinator writes them."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

from harness.console.orchestration_events import (
    POLL_INTERVAL_SECONDS,
    OrchestrationEvents,
)
from harness.console.server import MAX_SUBSCRIPTIONS, ConsoleServer
from harness.console.snapshots import SnapshotService
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from tests.console._console_ledger_fixture import _Batch
from tests.console.test_server import GatedCollect, _connect

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

INTERVAL = 0.2


def _subscribe(id: object = 1, **fields: object) -> str:
    return json.dumps({"id": id, "type": "orchestration.subscribe", **fields})


async def _receive(client: ClientConnection, timeout: float = 5):  # type: ignore[no-untyped-def]
    return json.loads(await asyncio.wait_for(client.recv(), timeout))


async def _events(  # type: ignore[no-untyped-def]
    client: ClientConnection, count: int, timeout: float = 5
):
    """The next `count` events, across as many `events` messages as they take."""
    found: list[dict[str, object]] = []
    while len(found) < count:
        message = await _receive(client, timeout)
        assert message["ok"] is True, message
        if message["kind"] == "events":
            found.extend(message["events"])
    return found


def _ledger(project: Path) -> LifecycleLedger:
    ledger = LifecycleLedger(project / STATE_REL)
    ledger.ensure()
    return ledger


def _server(project: Path) -> ConsoleServer:
    return ConsoleServer(
        project,
        events=OrchestrationEvents(project, interval=INTERVAL),
        snapshots=SnapshotService(project, collect=GatedCollect(open_gate=True)),
    )


def test_the_poll_interval_is_one_second() -> None:
    assert POLL_INTERVAL_SECONDS == 1.0


def test_batch_dispatch_gate_and_qa_events_reach_a_subscriber(project: Path) -> None:
    ledger = _ledger(project)
    batch = _Batch(ledger, "batch-a", "#7")
    batch.save("awaiting-approval")

    async def scenario() -> None:
        loop = asyncio.get_running_loop()
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                first = await _receive(client)
                assert (first["id"], first["type"], first["ok"]) == (
                    "live",
                    "orchestration.subscribe",
                    True,
                )
                assert first["kind"] == "source"
                assert first["source"]["state"] == "available"
                assert first["source"]["store"] == "ledger"
                assert first["source"]["reason"] is None

                started = loop.time()
                batch.dispatch("dispatch-dev", "developer")
                events = await _events(client, 2)
                assert loop.time() - started <= 1.0
                assert [event["event"] for event in events] == [
                    "batch.transition",
                    "dispatch.transition",
                ]
                assert events[0]["batch_id"] == "batch-a"
                assert (events[0]["ticket"], events[0]["from"], events[0]["to"]) == (
                    "#7",
                    "awaiting-approval",
                    "active",
                )
                assert (
                    events[1]["dispatch_id"],
                    events[1]["role"],
                    events[1]["from"],
                    events[1]["to"],
                ) == ("dispatch-dev", "developer", None, "dispatched")
                assert events[1]["seq"] == events[0]["seq"] + 1

                batch.report("dispatch-dev", "developer", "completed", output="ok")
                batch.decide("dispatch-dev", "accept", next_role="qa")
                batch.save()
                events = await _events(client, 3)
                assert [event["event"] for event in events] == [
                    "batch.transition",
                    "dispatch.transition",
                    "gate.decision",
                ]
                gate = events[2]
                assert (gate["dispatch_id"], gate["decision"], gate["next_role"]) == (
                    "dispatch-dev",
                    "accept",
                    "qa",
                )
                assert gate["approved_by"] == "coordinator"

                batch.dispatch("dispatch-qa", "qa")
                await _events(client, 2)
                batch.report("dispatch-qa", "qa", "completed", output="QA passed")
                events = await _events(client, 3)
                assert events[-1]["event"] == "qa.run"
                assert (events[-1]["dispatch_id"], events[-1]["outcome"]) == (
                    "dispatch-qa",
                    "completed",
                )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_orchestration_subscriptions_leave_request_slots_free(project: Path) -> None:
    _ledger(project)

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                for index in range(MAX_SUBSCRIPTIONS):
                    await client.send(_subscribe(index))
                    assert (await _receive(client))["kind"] == "source"
                await client.send(_subscribe("extra"))
                refused = await _receive(client)
                assert (refused["id"], refused["error"]["code"]) == ("extra", "busy")
                await client.send(json.dumps({"id": "home", "type": "home.snapshot"}))
                answered = await _receive(client)
                assert (answered["id"], answered["ok"]) == ("home", True)
        finally:
            await server.close()

    asyncio.run(scenario())


def test_a_malformed_subscription_is_a_bad_request(project: Path) -> None:
    _ledger(project)

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("extra", force=True))
                reply = await _receive(client)
                assert (reply["ok"], reply["error"]["code"]) == (False, "bad_request")
                await client.send(_subscribe("cursor", cursor=5))
                reply = await _receive(client)
                assert (reply["ok"], reply["error"]["code"]) == (False, "bad_request")
        finally:
            await server.close()

    asyncio.run(scenario())
