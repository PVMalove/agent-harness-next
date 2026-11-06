"""The request router owns the per-connection slots without any transport."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import cast

import pytest

from harness.console.backend.api import request_router
from harness.console.backend.api.request_router import (
    MAX_SUBSCRIPTIONS,
    MAX_UNFINISHED_REQUESTS,
    RequestRouter,
)
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.backend.application.worker_steps import WorkerStepsQuery


class Gate:
    def __init__(self) -> None:
        self.open = asyncio.Event()
        self.cancelled = 0

    async def wait(self) -> None:
        try:
            await self.open.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise


def _router(
    monkeypatch: pytest.MonkeyPatch, gate: Gate
) -> tuple[RequestRouter, list[dict[str, object]]]:
    async def respond(raw: str, snapshots: SnapshotService) -> str:
        await gate.wait()
        return json.dumps({"id": json.loads(raw)["id"], "ok": True})

    async def job_replies(raw: str, jobs: JobService) -> AsyncGenerator[str, None]:
        await gate.wait()
        yield json.dumps({"id": json.loads(raw)["id"], "ok": True})

    monkeypatch.setattr(request_router, "respond", respond)
    monkeypatch.setattr(request_router, "job_replies", job_replies)
    monkeypatch.setattr(request_router, "worker_replies", job_replies)
    sent: list[dict[str, object]] = []
    router = RequestRouter(
        cast(SnapshotService, object()),
        cast(JobService, object()),
        cast(DecisionService, object()),
        cast(OrchestrationEvents, object()),
        cast(ScreenService, object()),
        cast(WorkerStepsQuery, object()),
    )
    return router, sent


def _home(id: int) -> str:
    return json.dumps({"id": id, "type": "home.snapshot"})


def _subscribe(id: int) -> str:
    return json.dumps({"id": id, "type": "job.subscribe", "job_id": "j"})


async def _settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


def test_the_fifth_unfinished_request_gets_busy_and_finished_ones_free_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        gate = Gate()
        router, sent = _router(monkeypatch, gate)

        async def send(reply: str) -> bool:
            sent.append(json.loads(reply))
            return True

        connection = router.open(send)
        for id in range(1, MAX_UNFINISHED_REQUESTS + 2):
            await connection.submit(_home(id))
        await _settle()
        assert len(sent) == 1
        assert sent[0]["id"] == 5 and sent[0]["error"] == {
            "code": "busy",
            "message": sent[0]["error"]["message"],  # type: ignore[index]
        }
        gate.open.set()
        await _settle()
        assert {reply["id"] for reply in sent[1:]} == {1, 2, 3, 4}
        assert connection.unfinished == 0
        await connection.submit(_home(6))
        await _settle()
        assert sent[-1] == {"id": 6, "ok": True}
        await connection.aclose()

    asyncio.run(scenario())


def test_subscriptions_have_their_own_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        gate = Gate()
        router, sent = _router(monkeypatch, gate)

        async def send(reply: str) -> bool:
            sent.append(json.loads(reply))
            return True

        connection = router.open(send)
        for id in range(1, MAX_UNFINISHED_REQUESTS + 1):
            await connection.submit(_home(id))
        for id in range(10, 10 + MAX_SUBSCRIPTIONS):
            await connection.submit(_subscribe(id))
        await _settle()
        assert sent == []
        assert connection.unfinished == MAX_UNFINISHED_REQUESTS + MAX_SUBSCRIPTIONS
        await connection.submit(_subscribe(99))
        assert [reply["id"] for reply in sent] == [99]
        await connection.aclose()

    asyncio.run(scenario())


def test_worker_subscribe_takes_a_subscription_slot_and_steps_a_request_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        gate = Gate()
        router, sent = _router(monkeypatch, gate)

        async def send(reply: str) -> bool:
            sent.append(json.loads(reply))
            return True

        connection = router.open(send)

        def worker(id: int, kind: str) -> str:
            return json.dumps({"id": id, "type": kind, "dispatch_id": "d", "offset": 0})

        for id in range(1, MAX_SUBSCRIPTIONS + 1):
            await connection.submit(worker(id, "worker.subscribe"))
        for id in range(10, 10 + MAX_UNFINISHED_REQUESTS):
            await connection.submit(worker(id, "worker.steps"))
        await _settle()
        assert sent == []
        await connection.submit(worker(98, "worker.subscribe"))
        await connection.submit(worker(99, "worker.steps"))
        assert [reply["id"] for reply in sent] == [98, 99]
        gate.open.set()
        await _settle()
        assert {reply["id"] for reply in sent[2:]} == {
            *range(1, MAX_SUBSCRIPTIONS + 1),
            *range(10, 10 + MAX_UNFINISHED_REQUESTS),
        }
        await connection.aclose()

    asyncio.run(scenario())


def test_aclose_cancels_unfinished_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        gate = Gate()
        router, sent = _router(monkeypatch, gate)

        async def send(reply: str) -> bool:
            sent.append(json.loads(reply))
            return True

        connection = router.open(send)
        await connection.submit(_home(1))
        await connection.submit(_subscribe(2))
        await _settle()
        await connection.aclose()
        assert gate.cancelled == 2
        assert connection.unfinished == 0
        assert sent == []

    asyncio.run(scenario())


def test_a_gone_peer_stops_a_stream_and_a_failure_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        gate = Gate()
        gate.open.set()
        router, _ = _router(monkeypatch, gate)
        failures: list[str] = []

        async def gone(reply: str) -> bool:
            return False

        connection = router.open(gone, lambda: failures.append("failed"))
        await connection.submit(_subscribe(1))
        await _settle()
        assert connection.unfinished == 0 and failures == []

        async def broken(reply: str) -> bool:
            raise ConnectionError("peer reset")

        connection = router.open(broken, lambda: failures.append("failed"))
        await connection.submit(_home(2))
        await _settle()
        assert failures == ["failed"]

    asyncio.run(scenario())
