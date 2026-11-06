"""The task-board requests round-trip through the FastAPI application: the real /ws route and its
security middleware, driven in process over ASGI (tests/console/README.md forbids sockets) with a
fake GitHub tracker runner and a ledger fixture."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.backend.application.task_board import TaskBoardService
from harness.console.backend.infrastructure.task_board_tracker import (
    TrackerBoardReader,
    read_only,
)
from harness.console.kernel.protocol import MESSAGE_LIMIT
from harness.console.kernel.reports import BatchSummary, LedgerView, StageEntry
from harness.health.project_tracker import ProjectTracker

from ._asgi_ws import AsgiWebSocket
from ._screen_facts import Clock, Facts
from .test_server_screens import PORT, TOKEN, Runtime

GITHUB = ProjectTracker("github", "github.com", "acme/app", "config")
SPEC_BODY = "## Integration Branch\n`integration/web-console`\n"
TICKET_BODY = """## What to build
Build the board.

## Acceptance criteria
- [ ] Columns follow the table

## Relevant Files (Discovery Context)
- `harness/console/` — console

## Blocked by
- Blocked by #903 — needs ready
"""


def _node(
    number: int, labels: list[str], *, closed: bool = False, body: str = TICKET_BODY
) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Ticket {number}",
        "url": f"https://github.com/acme/app/issues/{number}",
        "state": "CLOSED" if closed else "OPEN",
        "body": body,
        "labels": {"nodes": [{"name": name} for name in labels]},
        "blockedBy": {"nodes": []},
    }


class Tracker:
    """A fake GitHub behind the process runner; every argv is recorded."""

    def __init__(self) -> None:
        self.nodes = [
            _node(901, ["afk", "pipeline::fast", "status::blocked"]),
            _node(902, ["afk"]),
            _node(903, ["hitl", "status::ready"]),
            _node(904, ["afk", "pipeline::full", "status::in-progress"]),
            _node(905, ["afk", "status::in-progress"]),
            _node(906, ["afk", "status::in-progress"]),
            _node(907, ["afk", "status::in-progress"]),
            _node(908, ["afk", "status::in-progress"], closed=True),
            _node(909, ["resolution::wontfix"], closed=True),
            _node(910, ["afk", "status::ready"]),
        ]
        self.failing = False
        self.calls: list[list[str]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        timeout: float,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if self.failing:
            return subprocess.CompletedProcess(argv, 1, "", "gh auth login required")
        if argv[:2] == ["gh", "pr"]:
            pulls = [
                {
                    "number": 958,
                    "url": "https://github.com/acme/app/pull/958",
                    "headRefName": "feature/issue-907-x",
                },
                {
                    "number": 959,
                    "url": "https://github.com/acme/app/pull/959",
                    "headRefName": "feature/issue-910-y",
                },
            ]
            return subprocess.CompletedProcess(argv, 0, json.dumps(pulls), "")
        query = next(arg for arg in argv if arg.startswith("query="))
        if "subIssues(" in query:
            if "number=862" not in argv:
                data: dict[str, object] = {"data": {"repository": {"issue": None}}}
            else:
                data = {
                    "data": {
                        "repository": {
                            "issue": {
                                "number": 862,
                                "title": "Web console",
                                "url": "https://github.com/acme/app/issues/862",
                                "body": SPEC_BODY,
                                "subIssues": {"nodes": self.nodes},
                            }
                        }
                    }
                }
        else:
            data = {
                "data": {
                    "repository": {
                        "issues": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [
                                {
                                    "number": 862,
                                    "title": "Web console",
                                    "url": "https://github.com/acme/app/issues/862",
                                    "body": SPEC_BODY,
                                    "subIssuesSummary": {
                                        "total": len(self.nodes),
                                        "completed": 2,
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        return subprocess.CompletedProcess(argv, 0, json.dumps(data), "")


def _ledger(repo: Path) -> LedgerView:
    at = "2026-11-06T0{}:00:00Z"
    return LedgerView(
        batches=[
            BatchSummary("b-904", "#904", "active", at.format(1)),
            BatchSummary("b-905", "#905", "active", at.format(1)),
            BatchSummary("b-906", "#906", "active", at.format(1)),
            BatchSummary("b-old", "#903", "completed", at.format(1)),
        ],
        stages=[
            StageEntry("d-1", "b-904", "#904", "developer", "working", at.format(2)),
            StageEntry("d-2", "b-905", "#905", "developer", "completed", at.format(2)),
            StageEntry("d-3", "b-905", "#905", "code-review", "working", at.format(3)),
            StageEntry("d-4", "b-906", "#906", "qa", "working", at.format(3)),
            StageEntry("d-5", "b-old", "#903", "qa", "working", at.format(4)),
        ],
    )


def _runtime(tmp_path: Path, tracker: Tracker) -> Runtime:
    facts, clock = Facts(), Clock()
    board = TaskBoardService(
        tmp_path,
        clock=clock,
        reader=TrackerBoardReader(
            runner=tracker,
            clock=clock,
            resolve=lambda repo: GITHUB,
            which=lambda name: f"/usr/bin/{name}",
        ),
        ledger=_ledger,
    )
    screens = ScreenService(
        tmp_path,
        clock=clock,
        ledger=facts.ledger,
        ledger_online=facts.ledger_online,
        lock=facts.lock,
        recovery=facts,
        route=facts,
        board=board,
    )
    parts = composition.compose(
        tmp_path,
        snapshots=cast(SnapshotService, object()),
        jobs=cast(JobService, object()),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=screens,
    )
    return Runtime(parts.router, tmp_path / "no-build")


async def _frame(socket: AsgiWebSocket, frames: list[int]) -> dict[str, object]:
    text = await socket.receive_text()
    frames.append(len(text.encode("utf-8", errors="surrogatepass")))
    reply = json.loads(text)
    assert isinstance(reply, dict)
    return reply


async def _read(
    socket: AsgiWebSocket, request: dict[str, object], frames: list[int] | None = None
) -> tuple[dict[str, object], dict[str, object]]:
    """The first reply and the reassembled payload of a paged request."""
    frames = [] if frames is None else frames
    await socket.send_text(json.dumps({"id": 1, **request}))
    first = reply = await _frame(socket, frames)
    assert reply["ok"] is True, reply
    text = cast(str, reply["text"])
    while not reply["done"]:
        await socket.send_text(
            json.dumps(
                {
                    "id": 2,
                    "type": "snapshot.page",
                    "snapshot_id": first["snapshot_id"],
                    "offset": reply["next"],
                }
            )
        )
        reply = await _frame(socket, frames)
        assert reply["ok"] is True, reply
        text += cast(str, reply["text"])
    payload = json.loads(text)
    assert isinstance(payload, dict)
    return first, payload


def _cards(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        cast(str, card["id"]): card
        for card in cast(list[dict[str, object]], payload["tickets"])
    }


async def _error(socket: AsgiWebSocket, request: dict[str, object]) -> str:
    await socket.send_text(json.dumps({"id": 7, **request}))
    reply = json.loads(await socket.receive_text())
    assert reply["ok"] is False and reply["id"] == 7, reply
    return cast(str, reply["error"]["code"])


def test_the_board_round_trips_with_every_column_row(tmp_path: Path) -> None:
    tracker = Tracker()
    runtime = _runtime(tmp_path, tracker)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            reply, specs = await _read(socket, {"type": "task_board.specs"})
            assert reply["type"] == "task_board.specs" and reply["cached"] is False
            assert specs["tracker"] == "github"
            assert [
                spec["id"] for spec in cast(list[dict[str, object]], specs["specs"])
            ] == ["#862"]
            reply, board = await _read(
                socket, {"type": "task_board.snapshot", "spec": "#862"}
            )
            assert reply["type"] == "task_board.snapshot"
            cards = _cards(board)
            assert {ref: card["column"] for ref, card in cards.items()} == {
                "#901": "backlog",
                "#902": "backlog",
                "#903": "ready",
                "#904": "progress",
                "#905": "review",
                "#906": "review",
                "#907": "review",
                "#908": "done",
                "#910": "ready",
            }
            assert cards["#905"]["dispatch"] == "code-review"
            assert cards["#903"]["batch"] is None
            prompts = {ref: cast(str, card["prompt"]) for ref, card in cards.items()}
            assert prompts["#901"].startswith("/fast-implement #901\n")
            assert prompts["#902"].startswith("/implement #902\n")
            assert prompts["#903"].startswith("/to-guide #903\n")
            assert prompts["#904"].startswith("/implement #904\n")
            for part in (
                "TICKET: #901 — Ticket 901",
                "EPIC: #862 — Web console",
                "BRANCH: integration/web-console",
                "WHAT TO BUILD:\nBuild the board.",
                "ACCEPTANCE:\n1. Columns follow the table",
                "BLOCKERS:\n- #903 — needs ready",
                "DISCOVERY:\n- harness/console/ — console",
            ):
                assert part in prompts["#901"]
            assert cards["#901"]["blockers"] == [
                {"id": "#903", "n": 903, "why": "needs ready", "state": "open"}
            ]
            assert board["kpis"] == {
                "open": 8,
                "total": 9,
                "with_open_blockers": 9,
                "active_batch": 3,
            }
            assert (
                await _error(socket, {"type": "task_board.snapshot", "spec": "#1"})
                == "not_found"
            )
            assert (
                await _error(socket, {"type": "task_board.snapshot"}) == "bad_request"
            )
            assert (
                await _error(
                    socket, {"type": "task_board.snapshot", "spec": "#862", "x": 1}
                )
                == "bad_request"
            )
            assert (
                await _error(socket, {"type": "task_board.specs", "force": "yes"})
                == "bad_request"
            )
        assert all(read_only(argv) for argv in tracker.calls)

    asyncio.run(scenario())


def test_force_shows_a_new_sub_ticket_and_an_outage_keeps_the_last_board(
    tmp_path: Path,
) -> None:
    tracker = Tracker()
    runtime = _runtime(tmp_path, tracker)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            await _read(socket, {"type": "task_board.snapshot", "spec": "#862"})
            tracker.nodes.append(_node(911, ["afk", "status::ready"]))
            cached, board = await _read(
                socket, {"type": "task_board.snapshot", "spec": "#862"}
            )
            assert cached["cached"] is True and "#911" not in _cards(board)
            forced, board = await _read(
                socket, {"type": "task_board.snapshot", "spec": "#862", "force": True}
            )
            assert (
                forced["cached"] is False and _cards(board)["#911"]["column"] == "ready"
            )
            tracker.failing = True
            stale_reply, stale = await _read(
                socket, {"type": "task_board.snapshot", "spec": "#862", "force": True}
            )
            assert stale_reply["cached"] is True
            assert (
                isinstance(stale["stale"], dict) and stale["stale"]["reason"] == "auth"
            )
            assert stale["age_seconds"] == 0.0
            assert "#911" in _cards(stale)
            _, specs = await _read(socket, {"type": "task_board.specs"})
            assert (
                specs["specs"] == []
                and cast(dict[str, str], specs["stale"])["reason"] == "auth"
            )

    asyncio.run(scenario())


def test_hostile_ticket_text_fits_the_message_limit(tmp_path: Path) -> None:
    tracker = Tracker()
    hostile = "## What to build\n" + ('\ud800\x00"\\é😀' * 20_000)
    tracker.nodes = [
        _node(n, ["afk", "status::ready"], body=hostile) for n in range(1, 21)
    ]
    runtime = _runtime(tmp_path, tracker)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            frames: list[int] = []
            _, board = await _read(
                socket, {"type": "task_board.snapshot", "spec": "#862"}, frames
            )
            assert len(frames) > 1
            assert max(frames) <= MESSAGE_LIMIT
            assert len(_cards(board)) == 20
            assert board["truncated"] is True

    asyncio.run(scenario())
