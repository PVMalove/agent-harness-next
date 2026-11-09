"""The task-board service: the per-key TTL cache with force, the last-good fallback with its age
and reason when the tracker is unavailable, single-flight collects and the ledger stages."""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.application.ports import SpecNotFound, TrackerUnavailable
from harness.console.backend.application.screens import NotFound
from harness.console.backend.application.task_board import (
    BoardServed,
    TaskBoardService,
)
from harness.console.backend.domain.task_board import (
    BOARD_TTL_SECONDS,
    KEPT_BOARDS,
    SpecTickets,
    TrackerSpec,
    TrackerTicket,
)

SPEC = TrackerSpec("#862", 862, "Web console", None, "", 1, 1)


def _ticket(n: int, *labels: str) -> TrackerTicket:
    return TrackerTicket(f"#{n}", n, f"T{n}", None, False, labels, "")


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class FakeReader:
    """Answers from mutable tracker state and logs every read."""

    def __init__(self) -> None:
        self.tickets = [_ticket(913, "status::in-progress")]
        self.failure: TrackerUnavailable | None = None
        self.calls: list[str] = []
        self.gate: threading.Event | None = None

    def tracker_type(self, repo: Path) -> str:
        return "github"

    def specs(self, repo: Path) -> tuple[TrackerSpec, ...]:
        self.calls.append("specs")
        if self.failure is not None:
            raise self.failure
        return (SPEC,)

    def board(self, repo: Path, spec_ref: str) -> SpecTickets:
        self.calls.append(f"board {spec_ref}")
        if self.gate is not None:
            self.gate.wait(5)
        if self.failure is not None:
            raise self.failure
        if spec_ref == "#404":
            raise SpecNotFound(spec_ref)
        return SpecTickets(
            TrackerSpec(spec_ref, None, spec_ref, None, "", None, None),
            tuple(self.tickets),
            {},
        )


@dataclass
class _Batch:
    batch_id: str
    ticket: str
    state: str
    created_at: str


@dataclass
class _Stage:
    batch_id: str
    role: str
    state: str
    at: str


@dataclass
class _View:
    batches: list[_Batch] = field(default_factory=list)
    stages: list[_Stage] = field(default_factory=list)
    unavailable: str | None = None


def _ledger(repo: Path) -> _View:
    return _View(
        [_Batch("b-913", "#913", "active", "2026-11-06T00:00:00Z")],
        [_Stage("b-913", "qa", "working", "2026-11-06T01:00:00Z")],
    )


def _cards(served: BoardServed) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], served.payload["tickets"])


def _service(
    reader: FakeReader, clock: Clock, ledger: object = _ledger
) -> TaskBoardService:
    return TaskBoardService(
        Path("/repo"),
        clock=clock,
        reader=reader,
        ledger=ledger,  # type: ignore[arg-type]
    )


def test_board_is_cached_within_ttl_and_rebuilt_after_it() -> None:
    reader, clock = FakeReader(), Clock()
    service = _service(reader, clock)

    async def scenario() -> None:
        first = await service.board("#862")
        clock.now += BOARD_TTL_SECONDS - 1
        second = await service.board("#862")
        assert first.cached is False and first.age_seconds == 0.0
        assert second.cached is True and second.age_seconds == BOARD_TTL_SECONDS - 1
        assert reader.calls == ["board #862"]
        reader.tickets.append(_ticket(914, "status::ready"))
        clock.now += 1
        third = await service.board("#862")
        assert third.cached is False
        assert [card["id"] for card in _cards(third)] == ["#914", "#913"]

    asyncio.run(scenario())


def test_force_rebuilds_and_shows_a_new_sub_ticket() -> None:
    reader, clock = FakeReader(), Clock()
    service = _service(reader, clock)

    async def scenario() -> None:
        await service.board("#862")
        reader.tickets.append(_ticket(914))
        forced = await service.board("#862", force=True)
        assert [card["id"] for card in _cards(forced)] == ["#914", "#913"]
        assert reader.calls == ["board #862", "board #862"]

    asyncio.run(scenario())


class EarlyReader(FakeReader):
    """Reads the tickets before it waits on the gate, like a collect already under way."""

    def board(self, repo: Path, spec_ref: str) -> SpecTickets:
        self.calls.append(f"board {spec_ref}")
        tickets = tuple(self.tickets)
        if self.gate is not None:
            self.gate.wait(5)
        return SpecTickets(
            TrackerSpec(spec_ref, None, spec_ref, None, "", None, None), tickets, {}
        )


def test_force_during_a_collect_reads_the_tracker_again() -> None:
    reader, clock = EarlyReader(), Clock()
    reader.gate = threading.Event()
    service = _service(reader, clock)

    async def scenario() -> None:
        first = asyncio.create_task(service.board("#862"))
        await asyncio.sleep(0.05)
        reader.tickets.append(_ticket(914))
        forced = asyncio.create_task(service.board("#862", force=True))
        await asyncio.sleep(0.05)
        assert reader.gate is not None
        reader.gate.set()
        assert [card["id"] for card in _cards(await first)] == ["#913"]
        assert [card["id"] for card in _cards(await forced)] == ["#914", "#913"]
        assert reader.calls == ["board #862", "board #862"]

    asyncio.run(scenario())


def test_failures_of_unknown_boards_keep_the_last_good_boards() -> None:
    reader, clock = FakeReader(), Clock()
    service = _service(reader, clock)

    async def scenario() -> None:
        for n in range(KEPT_BOARDS):
            await service.board(f"#{n}")
        reader.failure = TrackerUnavailable("timeout", "gh did not answer in time")
        for n in range(100, 100 + KEPT_BOARDS):
            failed = await service.board(f"#{n}")
            assert failed.payload["tickets"] == [] and failed.stale is not None
        reader.calls.clear()
        kept = await service.board("#0")
        assert kept.cached is True and _cards(kept)
        assert reader.calls == []

    asyncio.run(scenario())


def test_tracker_failure_serves_the_last_payload_with_age_and_reason() -> None:
    reader, clock = FakeReader(), Clock()
    service = _service(reader, clock)

    async def scenario() -> None:
        await service.board("#862")
        reader.failure = TrackerUnavailable("auth", "gh: authentication required")
        clock.now += BOARD_TTL_SECONDS + 5
        served = await service.board("#862")
        assert served.cached is True
        assert served.age_seconds == BOARD_TTL_SECONDS + 5
        stale = {"reason": "auth", "message": "gh: authentication required"}
        assert served.stale == stale
        assert served.payload["stale"] == stale
        assert served.payload["age_seconds"] == BOARD_TTL_SECONDS + 5
        assert [card["id"] for card in _cards(served)] == ["#913"]
        clock.now += 1
        again = await service.board("#862")
        assert again.stale == stale
        assert reader.calls == ["board #862", "board #862"]

    asyncio.run(scenario())


def test_tracker_failure_without_data_serves_an_empty_payload() -> None:
    reader, clock = FakeReader(), Clock()
    reader.failure = TrackerUnavailable("timeout", "gh did not answer in time")
    service = _service(reader, clock)

    async def scenario() -> None:
        specs = await service.specs()
        board = await service.board("#862")
        assert specs.payload["specs"] == [] and specs.age_seconds is None
        assert specs.stale == {
            "reason": "timeout",
            "message": "gh did not answer in time",
        }
        assert board.payload["tickets"] == [] and board.cached is False
        assert board.payload["stale"] == specs.stale

    asyncio.run(scenario())


def test_unknown_spec_propagates() -> None:
    service = _service(FakeReader(), Clock())

    with pytest.raises(SpecNotFound):
        asyncio.run(service.board("#404"))


def test_collects_are_single_flight_and_survive_a_cancelled_waiter() -> None:
    reader, clock = FakeReader(), Clock()
    reader.gate = threading.Event()
    service = _service(reader, clock)

    async def scenario() -> None:
        first = asyncio.create_task(service.board("#862"))
        second = asyncio.create_task(service.board("#862"))
        await asyncio.sleep(0.05)
        first.cancel()
        assert reader.gate is not None
        reader.gate.set()
        served = await second
        assert served.payload["tickets"]
        assert reader.calls == ["board #862"]

    asyncio.run(scenario())


def test_ledger_stage_moves_a_ticket_to_review_and_its_failure_is_reported() -> None:
    reader, clock = FakeReader(), Clock()

    def broken(repo: Path) -> _View:
        raise OSError("ledger unreadable")

    async def scenario() -> None:
        ok = await _service(reader, clock).board("#862")
        assert ok.payload["ledger"] == "ok"
        assert _cards(ok)[0]["column"] == "review"
        assert _cards(ok)[0]["batch"] == "b-913"
        down = await _service(reader, clock, broken).board("#862")
        assert down.payload["ledger"] == "unavailable"
        assert _cards(down)[0]["column"] == "progress"

    asyncio.run(scenario())


def test_old_boards_are_evicted_beyond_the_limit() -> None:
    reader, clock = FakeReader(), Clock()
    service = _service(reader, clock)

    async def scenario() -> None:
        for n in range(KEPT_BOARDS + 1):
            await service.board(f"#{n}")
        reader.calls.clear()
        await service.board(f"#{KEPT_BOARDS}")
        await service.board("#0")
        assert reader.calls == ["board #0"]

    asyncio.run(scenario())


def test_screen_service_pages_the_board_payloads(tmp_path: Path) -> None:
    reader, clock = FakeReader(), Clock()
    screens = composition.screen_service(
        tmp_path, clock=clock, board=_service(reader, clock)
    )

    async def scenario() -> None:
        specs = await screens.task_board_specs()
        board = await screens.task_board("#862", force=True)
        assert json.loads(specs.text)["specs"][0]["id"] == "#862"
        assert specs.done and board.done
        assert json.loads(board.text)["spec"]["id"] == "#862"

    asyncio.run(scenario())
    assert set(reader.calls) == {"specs", "board #862"}


def test_screen_service_without_a_board_is_not_found(tmp_path: Path) -> None:
    screens = composition.screen_service(tmp_path, clock=Clock())
    screens_without = type(screens).__new__(type(screens))
    screens_without.__dict__.update(screens.__dict__)
    screens_without._board = None

    with pytest.raises(NotFound):
        asyncio.run(screens_without.task_board_specs())


def test_board_prompt_takes_the_blocks_of_the_project_prompt_file(tmp_path: Path) -> None:
    reader, clock = FakeReader(), Clock()
    sut = TaskBoardService(tmp_path, clock=clock, reader=reader, ledger=_ledger)  # type: ignore[arg-type]
    template = tmp_path / "docs" / "agents" / "agent-prompt.md"

    async def scenario() -> tuple[str, str]:
        without = str(_cards(await sut.board("#862"))[0]["prompt"])
        template.parent.mkdir(parents=True)
        template.write_text(
            "# Agent prompt\n\nIntro text.\n\n"
            "## Architecture invariants\n\n- One writer per entity.\n- No force push.\n"
            "### Storage\n# a shell comment\n- WAL only.\n\n"
            "## Implementation discipline\n\nRead the approved ADR first.\n",
            encoding="utf-8",
        )
        return without, str(_cards(await sut.board("#862", force=True))[0]["prompt"])

    without, prompt = asyncio.run(scenario())

    assert "ARCHITECTURE INVARIANTS" not in without
    assert "IMPLEMENTATION DISCIPLINE" not in without
    assert (
        "\n\nARCHITECTURE INVARIANTS (MANDATORY):\n- One writer per entity.\n- No force push.\n"
        "### Storage\n# a shell comment\n- WAL only.\n\nIMPLEMENTATION DISCIPLINE:"
    ) in prompt
    assert prompt.endswith("\n\nIMPLEMENTATION DISCIPLINE:\nRead the approved ADR first.")
    assert "Intro text." not in prompt
