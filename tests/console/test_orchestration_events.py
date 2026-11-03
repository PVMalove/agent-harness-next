"""Live orchestration events are tested on real loopback sockets over a fixture project: the
ledger records are written by the real `LifecycleLedger`, as the coordinator writes them."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

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


def _journal(project: Path) -> Path:
    from harness.console.discovery import discovery_path

    return discovery_path(project).with_name("orchestration-events.jsonl")


async def _source(server: ConsoleServer, project: Path, **fields: object) -> str:
    """The cursor that the first message of a new subscription carries."""
    async with _connect(server, project) as client:
        await client.send(_subscribe("probe", **fields))
        first = await _receive(client)
        assert first["kind"] == "source", first
        cursor = first["cursor"]
        assert isinstance(cursor, str)
        return cursor


def _seq(cursor: str) -> int:
    return int(cursor.rsplit("-", 1)[1])


def test_a_reconnect_after_a_server_restart_gets_every_missed_event(
    project: Path,
) -> None:
    ledger = _ledger(project)
    batch = _Batch(ledger, "batch-a", "#7")
    batch.save("awaiting-approval")

    async def scenario() -> None:
        first = _server(project)
        await first.start()
        try:
            async with _connect(first, project) as client:
                await client.send(_subscribe("live"))
                assert (await _receive(client))["kind"] == "source"
                batch.dispatch("dispatch-dev", "developer")
                message = await _receive(client)
                assert message["kind"] == "events"
                missed_from = message["cursor"]
                if len(message["events"]) < 2:
                    message = await _receive(client)
                    missed_from = message["cursor"]
                # Delivered by the first server after the client stopped reading.
                batch.report("dispatch-dev", "developer", "completed", output="ok")
                await _events(client, 2)
        finally:
            await first.close()
        # Written while no server runs.
        batch.decide("dispatch-dev", "accept", next_role="qa")
        batch.save()

        second = _server(project)
        await second.start()
        try:
            tails = []
            for attempt in ("again-1", "again-2"):
                async with _connect(second, project) as client:
                    await client.send(_subscribe(attempt, cursor=missed_from))
                    source = await _receive(client)
                    assert (source["kind"], source["cursor"]) == ("source", missed_from)
                    tails.append(await _events(client, 3))
            assert tails[0] == tails[1]
            assert [event["event"] for event in tails[0]] == [
                "batch.transition",
                "dispatch.transition",
                "gate.decision",
            ]
            assert [event["seq"] for event in tails[0]] == [
                _seq(missed_from) + offset for offset in (1, 2, 3)
            ]
        finally:
            await second.close()

    asyncio.run(scenario())


def test_a_restart_without_changes_gives_no_events(project: Path) -> None:
    ledger = _ledger(project)
    _Batch(ledger, "batch-a", "#7").save("awaiting-approval")

    async def scenario() -> None:
        first = _server(project)
        await first.start()
        try:
            head = await _source(first, project)
        finally:
            await first.close()
        second = _server(project)
        await second.start()
        try:
            async with _connect(second, project) as client:
                await client.send(_subscribe("again", cursor=head))
                assert (await _receive(client))["cursor"] == head
                try:
                    unexpected = await _receive(client, timeout=3 * INTERVAL)
                except TimeoutError:
                    unexpected = None
                assert unexpected is None
        finally:
            await second.close()

    asyncio.run(scenario())


def test_a_torn_journal_tail_is_dropped_and_seq_continues(project: Path) -> None:
    ledger = _ledger(project)
    batch = _Batch(ledger, "batch-a", "#7")
    batch.save("awaiting-approval")

    async def scenario() -> None:
        first = _server(project)
        await first.start()
        try:
            head = await _source(first, project)
        finally:
            await first.close()
        with _journal(project).open("ab") as journal:
            journal.write(b'{"head": 99, "events": [{"seq"')
        second = _server(project)
        await second.start()
        try:
            async with _connect(second, project) as client:
                await client.send(_subscribe("again", cursor=head))
                assert (await _receive(client))["cursor"] == head
                batch.dispatch("dispatch-dev", "developer")
                events = await _events(client, 2)
                assert [event["seq"] for event in events] == [
                    _seq(head) + 1,
                    _seq(head) + 2,
                ]
        finally:
            await second.close()
        assert _journal(project).read_bytes().endswith(b"\n")

    asyncio.run(scenario())


async def _refused(server: ConsoleServer, project: Path, cursor: str) -> str:
    async with _connect(server, project) as client:
        await client.send(_subscribe("refused", cursor=cursor))
        reply = await _receive(client)
        assert reply["ok"] is False, reply
        code = reply["error"]["code"]
        assert isinstance(code, str)
        return code


def test_foreign_expired_and_invalid_cursors_are_refused(project: Path) -> None:
    _ledger(project)

    async def scenario() -> None:
        first = _server(project)
        await first.start()
        try:
            head = await _source(first, project)
            journal_id = head.split("-")[0]
            foreign = ("0" if journal_id[0] != "0" else "1") + journal_id[1:]
            assert await _refused(first, project, "garbage") == "invalid_cursor"
            assert (
                await _refused(first, project, f"{journal_id}-01") == "invalid_cursor"
            )
            assert (
                await _refused(first, project, f"{journal_id}-{_seq(head) + 1}")
                == "invalid_cursor"
            )
            assert await _refused(first, project, f"{foreign}-0") == "cursor_expired"
        finally:
            await first.close()
        _journal(project).unlink()
        second = _server(project)
        await second.start()
        try:
            assert await _refused(second, project, head) == "cursor_expired"
            assert await _source(second, project) != head
        finally:
            await second.close()

    asyncio.run(scenario())


def test_a_cursor_below_the_kept_window_expires_after_compaction(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console import event_journal

    monkeypatch.setattr(event_journal, "_KEPT_EVENTS", 2)
    ledger = _ledger(project)

    async def scenario() -> None:
        first = _server(project)
        await first.start()
        try:
            start = await _source(first, project)
            async with _connect(first, project) as client:
                await client.send(_subscribe("live", cursor=start))
                await _receive(client)
                for index in range(6):
                    _Batch(ledger, f"batch-{index}", f"#{index}")
                    (event,) = await _events(client, 1)
                    assert event["event"] == "batch.transition"
                    head = f"{start.split('-')[0]}-{event['seq']}"
            assert await _refused(first, project, start) == "cursor_expired"
            kept = f"{start.split('-')[0]}-{_seq(head) - 1}"
            async with _connect(first, project) as client:
                await client.send(_subscribe("kept", cursor=kept))
                await _receive(client)
                (event,) = await _events(client, 1)
                assert event["seq"] == _seq(head)
        finally:
            await first.close()
        assert len(_journal(project).read_bytes().splitlines()) <= 1 + 2 * 2
        second = _server(project)
        await second.start()
        try:
            assert await _refused(second, project, start) == "cursor_expired"
            async with _connect(second, project) as client:
                await client.send(_subscribe("kept", cursor=kept))
                await _receive(client)
                (event,) = await _events(client, 1)
                assert event["seq"] == _seq(head)
        finally:
            await second.close()

    asyncio.run(scenario())
