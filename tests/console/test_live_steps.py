"""The live step feed of the web console over fakes: the roster from the journal view, the
allowlisted orchestration and agent steps, and which worker logs are read."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import replace

from harness.console.backend.application.events import JournalPage
from harness.console.backend.application.live_steps import (
    LiveSteps,
    RosterItem,
    StepsItem,
)
from harness.console.backend.application.worker_steps import WorkerNotFound
from harness.console.backend.domain.live_steps import (
    AgentStep,
    DispatchTiming,
    OrchestrationStep,
    RosterDispatch,
    chunks,
    dispatch_timing,
    followed,
    orchestration_step,
    roster_from_view,
    timed,
)
from harness.console.backend.domain.worker_steps import StepsPage, WorkerStep

LIVE = ("dispatched", "working")
NOW = "2026-11-06T10:00:00+00:00"


def _view(states: dict[str, str]) -> dict[str, object]:
    return {
        "store": "file",
        "batches": {
            "batch-1": {
                "ticket": "#885",
                "state": "active",
                "dispatches": [
                    ["dispatch-a", "architect", "reported"],
                    ["dispatch-d", "developer", "dispatched"],
                    ["dispatch-q", "qa", "dispatched"],
                ],
                "decisions": 1,
            }
        },
        "dispatch_states": states,
        "qa_outcomes": {},
        "qa_attempts": {},
    }


class Journal:
    def __init__(
        self, view: dict[str, object], events: list[dict[str, object]]
    ) -> None:
        self.journal_id = "0123456789abcdef"
        self.floor = 0
        self.view = view
        self.events = events
        self.started = 0

    async def ensure_started(self) -> None:
        self.started += 1

    def read_after(self, position: int, limit: int) -> JournalPage | None:
        head = self.floor + len(self.events)
        inside = self.floor <= position <= head
        return JournalPage(
            journal_id=self.journal_id,
            floor=self.floor,
            head=head,
            events=self.events[position - self.floor :][:limit] if inside else [],
            view=self.view,
            available=True,
        )


def _page(
    dispatch_id: str, steps: list[WorkerStep], offset: int, **fields: object
) -> StepsPage:
    page = StepsPage(
        dispatch_id=dispatch_id,
        source="structured",
        structure="available",
        state="connected",
        reason=None,
        message="",
        offset=offset,
        reset=False,
        more=False,
        last_step_age_seconds=0,
        steps=tuple(steps),
    )
    return replace(page, **fields)  # type: ignore[arg-type]


class Workers:
    """Serves each dispatch's log once from offset 0, then nothing new."""

    def __init__(self, pages: dict[str, StepsPage]) -> None:
        self.pages = pages
        self.reads: list[tuple[str, int]] = []

    async def read(self, dispatch_id: str, offset: int) -> StepsPage:
        self.reads.append((dispatch_id, offset))
        page = self.pages.get(dispatch_id)
        if page is None:
            raise WorkerNotFound(dispatch_id)
        if offset >= page.offset:
            return replace(page, steps=())
        return page


async def _no_sleep(_: float) -> None:
    await asyncio.sleep(0)


def _feed(journal: Journal, workers: Workers, **options: object) -> LiveSteps:
    options.setdefault("sleep", _no_sleep)
    return LiveSteps(
        journal,
        workers,
        now=lambda: NOW,
        live_states=LIVE,
        **options,  # type: ignore[arg-type]
    )


async def _take(
    items: AsyncGenerator[RosterItem | StepsItem, None], count: int
) -> list[RosterItem | StepsItem]:
    taken: list[RosterItem | StepsItem] = []
    async for item in items:
        taken.append(item)
        if len(taken) == count:
            break
    await items.aclose()
    return taken


def test_the_roster_comes_from_the_compact_view_with_status_states_winning() -> None:
    roster = roster_from_view(_view({"dispatch-d": "working"}))

    assert [entry.to_wire() for entry in roster] == [
        {
            "dispatch_id": "dispatch-a",
            "batch_id": "batch-1",
            "ticket": "#885",
            "role": "architect",
            "state": "reported",
            "batch_state": "active",
            "branch": "",
            "started_at": "",
            "last_event_at": "",
            "silent": False,
        },
        {
            "dispatch_id": "dispatch-d",
            "batch_id": "batch-1",
            "ticket": "#885",
            "role": "developer",
            "state": "working",
            "batch_state": "active",
            "branch": "",
            "started_at": "",
            "last_event_at": "",
            "silent": False,
        },
        {
            "dispatch_id": "dispatch-q",
            "batch_id": "batch-1",
            "ticket": "#885",
            "role": "qa",
            "state": "dispatched",
            "batch_state": "active",
            "branch": "",
            "started_at": "",
            "last_event_at": "",
            "silent": False,
        },
    ]
    assert roster_from_view(None) == ()
    assert roster_from_view({"batches": {"b": {"dispatches": [["x"]]}}}) == ()


def test_a_gate_decision_takes_its_role_and_ticket_from_the_roster() -> None:
    roster = roster_from_view(_view({}))
    step = orchestration_step(
        {
            "seq": 7,
            "observed_at": NOW,
            "event": "gate.decision",
            "batch_id": "batch-1",
            "dispatch_id": "dispatch-d",
            "decision": "accept",
            "next_role": "review",
            "approved_by": "policy:auto",
            "approved_at": NOW,
        },
        roster,
    )

    assert step is not None
    assert step.to_wire() == {
        "origin": "orchestration",
        "seq": 7,
        "observed_at": NOW,
        "event": "gate.decision",
        "batch_id": "batch-1",
        "dispatch_id": "dispatch-d",
        "ticket": "#885",
        "role": "developer",
        "from_state": None,
        "to_state": None,
        "decision": "accept",
        "next_role": "review",
        "outcome": None,
        "stage": None,
        "message": "",
    }
    batch = orchestration_step(
        {"seq": 1, "event": "batch.transition", "batch_id": "batch-1", "to": "active"},
        roster,
    )
    assert batch is not None and batch.role is None and batch.ticket == "#885"
    assert orchestration_step({"seq": 2, "event": "secret.dump"}, roster) is None


def test_ending_dispatches_are_read_first_and_the_cap_holds() -> None:
    roster = tuple(
        RosterDispatch(f"d{n}", "b", "#1", "developer", "working") for n in range(6)
    ) + (RosterDispatch("done", "b", "#1", "qa", "reported"),)

    chosen = followed(roster, {"done"}, LIVE, 4)

    assert [entry.dispatch_id for entry in chosen] == ["done", "d0", "d1", "d2"]


def test_chunks_keep_each_group_within_the_budget() -> None:
    step = AgentStep(
        "d", "b", "developer", "structured", "available", "log", "x" * 90, NOW
    )
    groups = chunks([step] * 10, budget=1000)

    assert sum(len(group) for group in groups) == 10
    assert len(groups) > 1
    assert all(isinstance(item, AgentStep) for group in groups for item in group)


def test_the_feed_sends_the_roster_then_orchestration_and_agent_steps() -> None:
    journal = Journal(
        _view({"dispatch-d": "working"}),
        [
            {
                "seq": 1,
                "observed_at": NOW,
                "event": "dispatch.transition",
                "batch_id": "batch-1",
                "dispatch_id": "dispatch-d",
                "role": "developer",
                "from": "dispatched",
                "to": "working",
            }
        ],
    )
    workers = Workers(
        {
            "dispatch-d": _page("dispatch-d", [WorkerStep("tool", "Read")], 120),
            "dispatch-q": _page(
                "dispatch-q",
                [WorkerStep("log", "Проверяю")],
                40,
                source="plain",
                structure="unavailable",
            ),
        }
    )

    items = asyncio.run(_take(_feed(journal, workers).subscribe(), 4))

    roster, events, developer, qa = items
    assert isinstance(roster, RosterItem) and roster.reset is True
    assert roster.orchestration == "available"
    assert isinstance(events, StepsItem)
    [transition] = events.steps
    assert isinstance(transition, OrchestrationStep)
    assert (transition.from_state, transition.to_state) == ("dispatched", "working")
    assert isinstance(developer, StepsItem) and isinstance(qa, StepsItem)
    assert [step.to_wire() for step in developer.steps] == [
        {
            "origin": "agent",
            "dispatch_id": "dispatch-d",
            "batch_id": "batch-1",
            "role": "developer",
            "source": "structured",
            "structure": "available",
            "kind": "tool",
            "text": "Read",
            "observed_at": NOW,
        }
    ]
    [plain] = qa.steps
    assert isinstance(plain, AgentStep)
    assert (plain.source, plain.structure, plain.role) == ("plain", "unavailable", "qa")
    assert journal.started == 1
    # The reported architect is never read: only live dispatches are followed.
    assert all(read[0] != "dispatch-a" for read in workers.reads)


def test_a_dispatch_that_left_a_live_state_is_read_to_the_end_and_dropped() -> None:
    journal = Journal(_view({"dispatch-d": "working", "dispatch-q": "reported"}), [])
    workers = Workers(
        {"dispatch-d": _page("dispatch-d", [WorkerStep("tool", "Edit")], 50)}
    )
    sleeps: list[float] = []
    drained = [10**6]

    async def sleep(seconds: float) -> None:
        # Three idle ticks after the drain, then a roster change ends the wait of the test.
        sleeps.append(seconds)
        if len(sleeps) == drained[0] + 3:
            journal.view = _view(
                {"dispatch-d": "reported", "dispatch-q": "reported", "dispatch-a": "x"}
            )
        await asyncio.sleep(0)

    async def scenario() -> list[tuple[str, int]]:
        items = _feed(journal, workers, sleep=sleep).subscribe()
        await anext(items)  # roster
        await anext(items)  # the developer steps
        journal.view = _view({"dispatch-d": "reported", "dispatch-q": "reported"})
        workers.pages["dispatch-d"] = _page(
            "dispatch-d", [WorkerStep("result", "done")], 80
        )
        roster = await anext(items)
        last = await anext(items)
        assert isinstance(roster, RosterItem) and roster.reset is False
        assert isinstance(last, StepsItem)
        assert [step.to_wire()["text"] for step in last.steps] == ["done"]
        reads = len(workers.reads)
        drained[0] = len(sleeps)
        changed = await anext(items)
        assert isinstance(changed, RosterItem)
        await items.aclose()
        return workers.reads[reads:]

    after = asyncio.run(scenario())

    assert after == []


def test_a_new_journal_resets_the_list_and_reads_the_logs_again() -> None:
    journal = Journal(_view({"dispatch-d": "working"}), [])
    workers = Workers(
        {"dispatch-d": _page("dispatch-d", [WorkerStep("tool", "Read")], 10)}
    )

    async def scenario() -> list[RosterItem | StepsItem]:
        items = _feed(journal, workers).subscribe()
        first = [await anext(items), await anext(items)]
        journal.journal_id = "fedcba9876543210"
        second = [await anext(items), await anext(items)]
        await items.aclose()
        return first + second

    roster, steps, again, replayed = asyncio.run(scenario())

    assert isinstance(roster, RosterItem) and roster.reset
    assert isinstance(again, RosterItem) and again.reset
    assert isinstance(steps, StepsItem) and isinstance(replayed, StepsItem)
    assert steps.steps == replayed.steps


def test_an_unknown_dispatch_is_skipped_without_ending_the_feed() -> None:
    journal = Journal(_view({"dispatch-d": "working"}), [])
    workers = Workers({})

    async def scenario() -> list[tuple[str, int]]:
        items = _feed(journal, workers).subscribe()
        await anext(items)
        for _ in range(5):
            await asyncio.sleep(0)
        journal.view = _view({"dispatch-d": "reported"})
        await anext(items)
        await items.aclose()
        return workers.reads

    reads = asyncio.run(scenario())

    assert ("dispatch-d", 0) in reads
    assert all(offset == 0 for _, offset in reads)


def test_a_live_dispatch_without_a_heartbeat_for_ten_minutes_is_silent() -> None:
    entry = roster_from_view(_view({"dispatch-d": "working"}))[1]
    timing = dispatch_timing(
        {"created_at": "2026-11-05T10:00:00+00:00"},
        {
            "heartbeat_at": "2026-11-05T10:05:00+00:00",
            "updated_at": "2026-11-05T10:01:00+00:00",
        },
    )
    assert timing == DispatchTiming(
        "2026-11-05T10:00:00+00:00", "2026-11-05T10:05:00+00:00"
    )
    quiet = timed(entry, timing, "2026-11-05T10:16:00+00:00")
    assert (quiet.started_at, quiet.last_event_at, quiet.silent) == (
        "2026-11-05T10:00:00+00:00",
        "2026-11-05T10:05:00+00:00",
        True,
    )
    assert not timed(entry, timing, "2026-11-05T10:10:00+00:00").silent
    assert timed(entry, None, "2026-11-05T10:16:00+00:00") == entry
    # No heartbeat yet: the dispatch's age decides.
    fresh = dispatch_timing({"created_at": "2026-11-05T10:00:00+00:00"}, None)
    assert fresh.last_event_at == ""
    assert timed(entry, fresh, "2026-11-05T10:30:00+00:00").silent


def test_the_feed_times_only_the_live_dispatches_of_its_roster() -> None:
    asked: list[str] = []

    async def timing(dispatch_id: str) -> DispatchTiming | None:
        asked.append(dispatch_id)
        return DispatchTiming("2026-11-06T09:00:00+00:00", "2026-11-06T09:55:00+00:00")

    journal = Journal(_view({"dispatch-d": "working"}), [])
    feed = _feed(journal, Workers({}), timing=timing)
    first = asyncio.run(_take(feed.subscribe(), 1))[0]
    assert isinstance(first, RosterItem)
    by_id = {entry.dispatch_id: entry for entry in first.dispatches}
    assert by_id["dispatch-d"].last_event_at == "2026-11-06T09:55:00+00:00"
    assert not by_id["dispatch-d"].silent
    assert by_id["dispatch-a"].started_at == ""
    assert set(asked) == {"dispatch-d", "dispatch-q"}
