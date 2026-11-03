"""Live orchestration events are tested on real loopback sockets over a fixture project: the
ledger records are written by the real `LifecycleLedger`, as the coordinator writes them."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from harness.console.orchestration_events import (
    POLL_INTERVAL_SECONDS,
    BatchFacts,
    Observation,
    OrchestrationEvents,
    ProjectReader,
    SourceUnavailable,
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


def _server(project: Path, reader: ProjectReader | None = None) -> ConsoleServer:
    return ConsoleServer(
        project,
        events=OrchestrationEvents(project, interval=INTERVAL, reader=reader),
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


def test_compaction_replaces_the_journal_only_after_closing_it(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows refuses to replace a file that the process still holds open."""
    import os

    from harness.console import event_journal

    monkeypatch.setattr(event_journal, "_KEPT_EVENTS", 2)
    journal = _journal(project)
    held: set[int] = set()
    real_open, real_close, real_replace = os.open, os.close, os.replace

    def tracking_open(path, flags, *args, **kwargs):  # type: ignore[no-untyped-def]
        fd = real_open(path, flags, *args, **kwargs)
        if Path(path) == journal:
            held.add(fd)
        return fd

    def tracking_close(fd: int) -> None:
        held.discard(fd)
        real_close(fd)

    def windows_replace(source, target):  # type: ignore[no-untyped-def]
        if Path(target) == journal and held:
            raise PermissionError("the journal is open in this process")
        real_replace(source, target)

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "close", tracking_close)
    monkeypatch.setattr(os, "replace", windows_replace)
    ledger = _ledger(project)

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                assert (await _next_source(client))["state"] == "available"
                for index in range(6):
                    _Batch(ledger, f"batch-{index}", f"#{index}")
                    (event,) = await _events(client, 1)
                    assert event["event"] == "batch.transition"
        finally:
            await server.close()
        assert len(journal.read_bytes().splitlines()) <= 1 + 2 * 2

    asyncio.run(scenario())


async def _home_answers(client: ClientConnection) -> bool:
    await client.send(json.dumps({"id": "home", "type": "home.snapshot"}))
    while True:
        reply = await _receive(client)
        if reply["id"] == "home":
            return bool(reply["ok"])


async def _next_source(client: ClientConnection):  # type: ignore[no-untyped-def]
    while True:
        message = await _receive(client)
        assert message["ok"] is True, message
        if message["kind"] == "source":
            return message["source"]


def test_a_missing_ledger_is_a_typed_state_and_delivery_resumes(project: Path) -> None:
    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                source = await _next_source(client)
                assert (source["state"], source["reason"], source["store"]) == (
                    "unavailable",
                    "missing",
                    None,
                )
                assert source["message"]
                assert await _home_answers(client)
                ledger = _ledger(project)
                source = await _next_source(client)
                assert (source["state"], source["reason"], source["store"]) == (
                    "available",
                    None,
                    "ledger",
                )
                _Batch(ledger, "batch-a", "#7")
                (event,) = await _events(client, 1)
                assert (event["event"], event["batch_id"], event["to"]) == (
                    "batch.transition",
                    "batch-a",
                    "planned",
                )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_an_unreadable_ledger_delivers_its_changes_once_readable(
    project: Path,
) -> None:
    ledger = _ledger(project)
    batch = _Batch(ledger, "batch-a", "#7")
    batch.save("awaiting-approval")
    pointer = project / STATE_REL / "ledger.json"
    readable = pointer.read_bytes()

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                assert (await _next_source(client))["state"] == "available"
                pointer.write_text("{not json", encoding="utf-8")
                source = await _next_source(client)
                assert (source["state"], source["reason"]) == (
                    "unavailable",
                    "unreadable",
                )
                assert await _home_answers(client)
                # The coordinator changes the batch while the console cannot read the ledger.
                changed = {**batch.record, "state": "active"}
                (batch.root / "batches" / "batch-a.json").write_text(
                    json.dumps(changed), encoding="utf-8"
                )
                pointer.write_bytes(readable)
                assert (await _next_source(client))["state"] == "available"
                (event,) = await _events(client, 1)
                assert (event["event"], event["from"], event["to"]) == (
                    "batch.transition",
                    "awaiting-approval",
                    "active",
                )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_an_unavailable_journal_is_a_typed_state(project: Path) -> None:
    ledger = _ledger(project)

    async def scenario() -> None:
        server = _server(project)
        await server.start()
        journal = _journal(project)
        target = journal.with_name("elsewhere.jsonl")
        target.write_text("", encoding="utf-8")
        journal.symlink_to(target)
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                source = await _next_source(client)
                assert (source["state"], source["reason"], source["store"]) == (
                    "unavailable",
                    "journal_unavailable",
                    None,
                )
                assert await _home_answers(client)
                journal.unlink()
                assert (await _next_source(client))["state"] == "available"
                _Batch(ledger, "batch-a", "#7")
                (event,) = await _events(client, 1)
                assert event["event"] == "batch.transition"
        finally:
            await server.close()

    asyncio.run(scenario())


class ScriptedReader:
    """Returns whatever observation the test set last."""

    def __init__(self, observation: Observation) -> None:
        self.observation = observation

    def read(self) -> Observation:
        return self.observation


def _one_batch(state: str) -> Observation:
    return Observation(
        store="ledger",
        batches={
            "batch-a": BatchFacts(ticket="#7", state=state, dispatches=(), decisions=())
        },
    )


def test_a_failing_poll_is_a_typed_state_and_the_poller_keeps_polling(
    project: Path,
) -> None:
    _ledger(project)
    reader = ScriptedReader(_one_batch("planned"))

    async def scenario() -> None:
        server = ConsoleServer(
            project,
            events=OrchestrationEvents(project, interval=INTERVAL, reader=reader),
            snapshots=SnapshotService(project, collect=GatedCollect(open_gate=True)),
        )
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                assert (await _next_source(client))["state"] == "available"
                # A record the view cannot be built from fails after the read succeeded.
                reader.observation = Observation(
                    store="ledger",
                    batches={"batch-a": "not batch facts"},  # type: ignore[dict-item]
                )
                source = await _next_source(client)
                assert (source["state"], source["reason"]) == (
                    "unavailable",
                    "unreadable",
                )
                assert source["message"]
                assert await _home_answers(client)
                # A lone surrogate in a ledger field must not stop the journal either.
                reader.observation = _one_batch("active\ud800x")
                assert (await _next_source(client))["state"] == "available"
                (event,) = await _events(client, 1)
                assert (event["event"], event["from"], event["to"]) == (
                    "batch.transition",
                    "planned",
                    "active\ud800x",
                )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_compaction_keeps_a_lone_surrogate_and_bounds_the_journal(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console import event_journal

    monkeypatch.setattr(event_journal, "_KEPT_EVENTS", 2)
    _ledger(project)
    reader = ScriptedReader(_one_batch("planned"))

    async def scenario() -> None:
        server = ConsoleServer(
            project,
            events=OrchestrationEvents(project, interval=INTERVAL, reader=reader),
            snapshots=SnapshotService(project, collect=GatedCollect(open_gate=True)),
        )
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                assert (await _next_source(client))["state"] == "available"
                previous = "planned"
                for index in range(6):
                    state = f"step-{index}\ud800"
                    reader.observation = _one_batch(state)
                    message = await _receive(client)
                    assert message["kind"] == "events", message
                    (event,) = message["events"]
                    assert (event["from"], event["to"]) == (previous, state)
                    previous = state
        finally:
            await server.close()
        assert len(_journal(project).read_bytes().splitlines()) <= 1 + 2 * 2

    asyncio.run(scenario())


def _store_epoch(project: Path) -> None:
    state = project / STATE_REL
    state.mkdir(parents=True)
    (state / "ledger.json").write_text(json.dumps({"version": 4}), encoding="utf-8")


class FakeStore:
    """`state.read` of a runtime store: the records by path and the store revision."""

    def __init__(self) -> None:
        self.revision = 1
        self.records: dict[str, dict[str, object]] = {
            "batches/batch-a.json": {
                "batch_id": "batch-a",
                "ticket": "#7",
                "state": "awaiting-approval",
                "dispatches": [],
            }
        }
        self.calls: list[tuple[list[str], list[str]]] = []
        self.down = False

    def __call__(
        self, collections: Sequence[str], paths: Sequence[str]
    ) -> tuple[Mapping[str, object], int | None]:
        if self.down:
            raise SourceUnavailable(
                "runtime_unavailable", "The runtime is not running."
            )
        self.calls.append((list(collections), list(paths)))
        if not collections and not paths:
            return {}, self.revision
        found = {
            path: record
            for path, record in self.records.items()
            if path in paths or path.split("/", 1)[0] in collections
        }
        return found, self.revision

    def change(self, path: str, record: dict[str, object]) -> None:
        self.records[path] = record
        self.revision += 1


def test_the_store_epoch_is_polled_by_revision(project: Path) -> None:
    _store_epoch(project)
    store = FakeStore()

    async def scenario() -> None:
        server = _server(project, ProjectReader(project, store_fetch=store))
        await server.start()
        try:
            async with _connect(server, project) as client:
                await client.send(_subscribe("live"))
                source = await _next_source(client)
                assert (source["state"], source["store"]) == (
                    "available",
                    "runtime-store",
                )
                store.calls.clear()
                await asyncio.sleep(3 * INTERVAL)
                assert store.calls
                assert all(call == ([], []) for call in store.calls)

                store.change(
                    "batches/batch-a.json",
                    {**store.records["batches/batch-a.json"], "state": "active"},
                )
                (event,) = await _events(client, 1)
                assert (event["event"], event["from"], event["to"]) == (
                    "batch.transition",
                    "awaiting-approval",
                    "active",
                )

                store.down = True
                source = await _next_source(client)
                assert (source["state"], source["reason"]) == (
                    "unavailable",
                    "runtime_unavailable",
                )
                assert await _home_answers(client)
                store.change(
                    "batches/batch-b.json",
                    {"batch_id": "batch-b", "ticket": "#8", "state": "planned"},
                )
                store.down = False
                source = await _next_source(client)
                assert (source["state"], source["store"]) == (
                    "available",
                    "runtime-store",
                )
                (event,) = await _events(client, 1)
                assert (event["batch_id"], event["from"], event["to"]) == (
                    "batch-b",
                    None,
                    "planned",
                )
        finally:
            await server.close()

    asyncio.run(scenario())


def test_an_unavailable_runtime_is_the_runtime_unavailable_reason(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.orchestration import runtime_client

    _store_epoch(project)
    codes = iter(["runtime_unavailable", "store_busy"])

    def call(self: object, operation: str, **fields: object) -> object:
        assert operation == "state.read"
        raise runtime_client.RuntimeClientError(
            next(codes), "no answer", remedy="start it", domain="transport"
        )

    monkeypatch.setattr(runtime_client.RuntimeClient, "call", call)
    reader = ProjectReader(project)
    for reason in ("runtime_unavailable", "unreadable"):
        with pytest.raises(SourceUnavailable) as raised:
            reader.read()
        assert raised.value.reason == reason
