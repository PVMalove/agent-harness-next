"""The worker steps requests round-trip through the FastAPI application: the real /ws route and
its security middleware, driven in process over ASGI with a temporary ledger and worker logs."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.request_router import (
    MAX_SUBSCRIPTIONS,
    RequestRouter,
)
from harness.console.backend.api.schemas import REPLIES
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel.protocol import MESSAGE_LIMIT

from ._asgi_ws import AsgiWebSocket

PORT = 48124
TOKEN = "w" * 43


class Runtime:
    port = PORT
    token = TOKEN
    closing = False

    def __init__(self, router: RequestRouter, static_root: Path) -> None:
        self.router = router
        self.static_root = static_root

    def client_opened(self) -> None:
        return None

    def client_closed(self) -> None:
        return None


def _runtime(repo: Path) -> Runtime:
    parts = composition.compose(
        repo,
        snapshots=cast(SnapshotService, object()),
        jobs=cast(JobService, object()),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=cast(ScreenService, object()),
        workers=composition.worker_steps_query(repo, poll_seconds=0.01),
    )
    return Runtime(parts.router, repo / "no-build")


def _project(repo: Path) -> Path:
    """A structured dispatch `dispatch-s` and an external one `dispatch-p`; returns the
    structured event log."""
    root = repo / ".harness/orchestration/state"
    (root / "dispatches").mkdir(parents=True)
    (root / "dispatch-status").mkdir()
    events = repo / ".harness/.sandboxes/logs/workers/launch-1/events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "SECRET"},
                        {"type": "tool_use", "name": "Read", "input": {"p": "SECRET"}},
                    ]
                },
            }
        )
        + "\n"
    )
    for dispatch_id, transport in (
        ("dispatch-s", "external"),
        ("dispatch-p", "external"),
    ):
        (root / "dispatches" / f"{dispatch_id}.json").write_text(
            json.dumps(
                {
                    "dispatch_id": dispatch_id,
                    "state": "working",
                    "resolved_transport": transport,
                    "report_staging_path": str(
                        repo / f".harness/.sandboxes/scratch/inbox/{dispatch_id}.json"
                    ),
                }
            )
        )
    (root / "dispatch-status/dispatch-s.json").write_text(
        json.dumps(
            {
                "dispatch_id": "dispatch-s",
                "state": "working",
                "adapter_receipt": {
                    "protocol": "harness-worker-v1",
                    "dispatch_id": "dispatch-s",
                    "log_path": str(events),
                },
            }
        )
    )
    return events


async def _ask(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
    await socket.send_text(json.dumps(request))
    reply = json.loads(await socket.receive_text())
    assert isinstance(reply, dict)
    return reply


def test_worker_steps_query_returns_allowlisted_steps_and_typed_states(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    runtime = _runtime(tmp_path)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            structured = await _ask(
                socket,
                {
                    "id": 1,
                    "type": "worker.steps",
                    "dispatch_id": "dispatch-s",
                    "offset": 0,
                },
            )
            plain = await _ask(
                socket,
                {
                    "id": 2,
                    "type": "worker.steps",
                    "dispatch_id": "dispatch-p",
                    "offset": 0,
                },
            )
            unknown = await _ask(
                socket,
                {
                    "id": 3,
                    "type": "worker.steps",
                    "dispatch_id": "dispatch-x",
                    "offset": 0,
                },
            )
            bad = await _ask(
                socket,
                {"id": 4, "type": "worker.steps", "dispatch_id": "../x", "offset": -1},
            )
        assert structured["ok"] is True, structured
        page = cast(dict[str, object], structured["page"])
        assert page["source"] == "structured"
        assert page["steps"] == [{"kind": "tool", "text": "Read"}]
        assert "SECRET" not in json.dumps(structured)
        plain_page = cast(dict[str, object], plain["page"])
        assert (plain_page["structure"], plain_page["state"], plain_page["reason"]) == (
            "unavailable",
            "unavailable",
            "log_missing",
        )
        assert cast(dict[str, object], unknown["error"])["code"] == "not_found"
        assert cast(dict[str, object], bad["error"])["code"] == "bad_request"
        for reply in (structured, plain, unknown, bad):
            REPLIES.validate_python(reply)

    asyncio.run(scenario())


def test_worker_subscribe_streams_new_steps_in_a_subscription_slot(
    tmp_path: Path,
) -> None:
    events = _project(tmp_path)
    runtime = _runtime(tmp_path)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            first = await _ask(
                socket,
                {"id": "s", "type": "worker.subscribe", "dispatch_id": "dispatch-s"},
            )
            with events.open("a") as stream:
                stream.write(json.dumps({"type": "result", "result": "done"}) + "\n")
            second = json.loads(await socket.receive_text())
            for id in range(MAX_SUBSCRIPTIONS - 1):
                await socket.send_text(
                    json.dumps(
                        {
                            "id": id,
                            "type": "worker.subscribe",
                            "dispatch_id": "dispatch-s",
                        }
                    )
                )
            seen: set[object] = set()
            while len(seen) < MAX_SUBSCRIPTIONS - 1:
                seen.add(json.loads(await socket.receive_text())["id"])
            busy = await _ask(
                socket,
                {"id": "b", "type": "worker.subscribe", "dispatch_id": "dispatch-s"},
            )
        assert first["type"] == "worker.subscribe"
        assert cast(dict[str, list[object]], first["page"])["steps"] == [
            {"kind": "tool", "text": "Read"}
        ]
        assert second["id"] == "s"
        assert second["page"]["steps"] == [{"kind": "result", "text": "done"}]
        assert second["page"]["offset"] == events.stat().st_size
        assert cast(dict[str, object], busy["error"])["code"] == "busy"
        REPLIES.validate_python(second)

    asyncio.run(scenario())


def test_a_full_page_stays_below_the_message_limit(tmp_path: Path) -> None:
    events = _project(tmp_path)
    with events.open("a") as stream:
        for _ in range(400):
            record = {"type": "result", "result": '"\\' * 2000}
            stream.write(json.dumps(record) + "\n")
    runtime = _runtime(tmp_path)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            await socket.send_text(
                json.dumps(
                    {
                        "id": 1,
                        "type": "worker.steps",
                        "dispatch_id": "dispatch-s",
                        "offset": 0,
                    }
                )
            )
            raw = await socket.receive_text()
        assert len(raw.encode("utf-8")) <= MESSAGE_LIMIT
        reply = json.loads(raw)
        assert reply["page"]["more"] is True
        assert reply["page"]["steps"]

    asyncio.run(scenario())
