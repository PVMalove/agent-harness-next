"""The live step feed round-trips through the FastAPI application: the real /ws route and its
security middleware, driven in process over ASGI, with the real event poller and journal over a
fake orchestration reader, and real worker logs of a Claude and a Codex dispatch."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.request_router import MAX_SUBSCRIPTIONS, RequestRouter
from harness.console.backend.api.schemas import REPLIES
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.backend.domain.events import BatchFacts, Observation
from harness.console.kernel.protocol import MESSAGE_LIMIT

from ._asgi_ws import AsgiWebSocket

PORT = 48125
TOKEN = "l" * 43
SECRETS = ("THINK-SECRET", "INPUT-SECRET", "RAW-SECRET", "PLAIN-THINK", "PLAIN-INPUT")


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


class Reader:
    """The orchestration source of one batch with a Claude developer and a Codex reviewer."""

    def __init__(self) -> None:
        self.developer = "working"

    def read(self) -> Observation:
        return Observation(
            store="file",
            batches={
                "batch-1": BatchFacts(
                    ticket="#885",
                    state="active",
                    dispatches=(
                        ("dispatch-s", "developer", "dispatched"),
                        ("dispatch-p", "review", "dispatched"),
                    ),
                    decisions=(),
                )
            },
            dispatch_states={"dispatch-s": self.developer, "dispatch-p": "working"},
        )


def _project(repo: Path) -> Path:
    """Ledger records of `dispatch-s` (structured log) and `dispatch-p` (Codex plain log);
    returns the structured log."""
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
                        {"type": "thinking", "thinking": "THINK-SECRET"},
                        {"type": "text", "text": "Читаю схему"},
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"path": "INPUT-SECRET"},
                        },
                    ]
                },
            }
        )
        + "\n"
        + '{"type": "unknown", "raw": "RAW-SECRET"}\n'
    )
    plain = repo / ".harness/.sandboxes/scratch/worker-logs/dispatch-p.log"
    plain.parent.mkdir(parents=True)
    plain.write_text(
        "codex\nПроверяю тесты\n"
        "thinking\nPLAIN-THINK\n"
        "exec\nbash -lc PLAIN-INPUT\n"
        'codex\n{"raw": "RAW-SECRET"}\n'
    )
    for dispatch_id in ("dispatch-s", "dispatch-p"):
        (root / "dispatches" / f"{dispatch_id}.json").write_text(
            json.dumps(
                {
                    "dispatch_id": dispatch_id,
                    "state": "working",
                    "resolved_transport": "external",
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


def _runtime(repo: Path, reader: Reader) -> Runtime:
    events = composition.orchestration_events(
        repo, reader=reader, interval=0.01, journal_path=repo / "journal.jsonl"
    )
    workers = composition.worker_steps_query(repo, poll_seconds=0.01)
    parts = composition.compose(
        repo,
        snapshots=cast(SnapshotService, object()),
        jobs=cast(JobService, object()),
        decisions=cast(DecisionService, object()),
        events=events,
        screens=cast(ScreenService, object()),
        workers=workers,
        steps=composition.live_steps(events, workers, poll_seconds=0.01),
    )
    return Runtime(parts.router, repo / "no-build")


async def _receive(socket: AsgiWebSocket) -> tuple[str, dict[str, object]]:
    raw = await socket.receive_text()
    reply = json.loads(raw)
    assert isinstance(reply, dict)
    return raw, reply


def test_steps_subscribe_streams_typed_allowlisted_steps_of_both_sources(
    tmp_path: Path,
) -> None:
    events = _project(tmp_path)
    reader = Reader()
    runtime = _runtime(tmp_path, reader)
    received: list[str] = []

    async def scenario() -> list[dict[str, object]]:
        replies: list[dict[str, object]] = []
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            await socket.send_text(json.dumps({"id": "f", "type": "steps.subscribe"}))
            steps: list[dict[str, object]] = []

            async def until(predicate: Callable[[dict[str, object]], bool]) -> None:
                while not any(predicate(step) for step in steps):
                    raw, reply = await _receive(socket)
                    received.append(raw)
                    replies.append(reply)
                    if reply.get("kind") == "steps":
                        steps.extend(cast(list[dict[str, object]], reply["steps"]))

            await until(lambda step: step.get("source") == "plain")
            await until(lambda step: step.get("text") == "Читаю схему")
            # A new worker step and a dispatch transition arrive without a new request.
            with events.open("a") as stream:
                stream.write(json.dumps({"type": "result", "result": "готово"}) + "\n")
            reader.developer = "reported"
            await until(lambda step: step.get("text") == "готово")
            await until(lambda step: step.get("to_state") == "reported")
        return replies

    replies = asyncio.run(scenario())

    roster = replies[0]
    assert (roster["type"], roster["kind"], roster["reset"]) == (
        "steps.subscribe",
        "roster",
        True,
    )
    steps = [
        step
        for reply in replies
        if reply.get("kind") == "steps"
        for step in cast(list[dict[str, object]], reply["steps"])
    ]
    agent = [step for step in steps if step["origin"] == "agent"]
    structured = [
        (step["kind"], step["text"]) for step in agent if step["source"] == "structured"
    ]
    assert structured[:2] == [("output", "Читаю схему"), ("tool", "Read")]
    plain = [step for step in agent if step["source"] == "plain"]
    assert [(step["kind"], step["text"]) for step in plain] == [
        ("log", "Проверяю тесты"),
        ("tool", "exec"),
    ]
    assert {(step["structure"], step["role"]) for step in plain} == {
        ("unavailable", "review")
    }
    transition = next(step for step in steps if step.get("to_state") == "reported")
    assert transition["origin"] == "orchestration"
    assert (transition["event"], transition["role"], transition["ticket"]) == (
        "dispatch.transition",
        "developer",
        "#885",
    )
    for raw in received:
        assert len(raw.encode("utf-8")) <= MESSAGE_LIMIT
        for secret in SECRETS:
            assert secret not in raw
    for step in agent:
        assert not str(step["text"]).lstrip().startswith(("{", "["))
        assert set(step) == {
            "origin",
            "dispatch_id",
            "batch_id",
            "role",
            "source",
            "structure",
            "kind",
            "text",
            "observed_at",
        }
    for reply in replies:
        REPLIES.validate_python(reply)


def test_steps_subscribe_takes_one_subscription_slot_and_refuses_extra_fields(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    runtime = _runtime(tmp_path, Reader())

    async def scenario() -> tuple[dict[str, object], dict[str, object]]:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            await socket.send_text(
                json.dumps({"id": "x", "type": "steps.subscribe", "cursor": "1"})
            )
            _, bad = await _receive(socket)
            for index in range(MAX_SUBSCRIPTIONS):
                await socket.send_text(
                    json.dumps({"id": index, "type": "steps.subscribe"})
                )
            seen: set[object] = set()
            while len(seen) < MAX_SUBSCRIPTIONS:
                seen.add((await _receive(socket))[1]["id"])
            await socket.send_text(json.dumps({"id": "b", "type": "steps.subscribe"}))
            while True:
                _, busy = await _receive(socket)
                if busy["id"] == "b":
                    return bad, busy

    bad, busy = asyncio.run(scenario())

    assert cast(dict[str, object], bad["error"])["code"] == "bad_request"
    assert cast(dict[str, object], busy["error"])["code"] == "busy"
    REPLIES.validate_python(bad)
    REPLIES.validate_python(busy)
