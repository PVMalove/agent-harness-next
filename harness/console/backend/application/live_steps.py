"""The live step feed of the web console: one stream that merges the orchestration events of the
console journal with the worker steps of the live dispatches.

One subscription takes one request slot, whatever the number of followed dispatches. The feed
only reads: the journal the poller of `OrchestrationEvents` writes and the worker logs through
`WorkerStepsQuery`. It runs no background task; the consumer drives every tick. The roster comes
first, again when it changes, and with ``reset`` when the list starts over: on a new journal or
after the position fell below the kept events, the backlog and the worker logs are sent again.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Collection
from dataclasses import dataclass
from typing import Protocol

from ..domain.live_steps import (
    DispatchTiming,
    RosterDispatch,
    Step,
    agent_steps,
    chunks,
    followed,
    orchestration_step,
    roster_from_view,
    timed,
)
from ..domain.worker_steps import StepsPage
from .events import JournalPage
from .ports import WallClock
from .worker_steps import WorkerNotFound

POLL_SECONDS = 1.0
BACKLOG_EVENTS = 200
MAX_FOLLOWED = 4
_BATCH_EVENTS = 32


class JournalSource(Protocol):
    async def ensure_started(self) -> None: ...

    def read_after(self, position: int, limit: int) -> JournalPage | None: ...


class WorkerPages(Protocol):
    async def read(self, dispatch_id: str, offset: int) -> StepsPage: ...


@dataclass(frozen=True)
class RosterItem:
    """The dispatches of the journal view and whether the orchestration source is readable;
    ``reset`` tells the client to drop the steps it holds."""

    dispatches: tuple[RosterDispatch, ...]
    orchestration: str
    reset: bool


@dataclass(frozen=True)
class StepsItem:
    """A non-empty group of steps in the order they were read."""

    steps: list[Step]


class LiveSteps:
    """The step feed of one console server; every subscription keeps its own positions."""

    def __init__(
        self,
        events: JournalSource,
        workers: WorkerPages,
        *,
        now: WallClock,
        live_states: Collection[str],
        poll_seconds: float = POLL_SECONDS,
        backlog: int = BACKLOG_EVENTS,
        max_followed: int = MAX_FOLLOWED,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        timing: Callable[[str], Awaitable[DispatchTiming | None]] | None = None,
    ) -> None:
        self._timing = timing
        self._events = events
        self._workers = workers
        self._now = now
        self._live = frozenset(live_states)
        self._poll = poll_seconds
        self._backlog = backlog
        self._cap = max_followed
        self._sleep = sleep

    async def _timed(
        self, roster: tuple[RosterDispatch, ...]
    ) -> tuple[RosterDispatch, ...]:
        """The roster with the timing of its live dispatches; the others keep none."""
        if self._timing is None:
            return roster
        now = self._now()
        found: list[RosterDispatch] = []
        for entry in roster:
            timing = await self._timing(entry.dispatch_id) if entry.state in self._live else None
            found.append(timed(entry, timing, now))
        return tuple(found)

    async def subscribe(self) -> AsyncGenerator[RosterItem | StepsItem, None]:
        """The roster and the steps until the subscriber stops."""
        await self._events.ensure_started()
        journal_id: str | None = None
        position = 0
        reset = True
        sent: tuple[tuple[RosterDispatch, ...], str] | None = None
        offsets: dict[str, int] = {}
        draining: set[str] = set()
        gone: set[str] = set()
        while True:
            more = False
            page = self._events.read_after(position, _BATCH_EVENTS)
            if page is not None and (
                page.journal_id != journal_id or not page.floor <= position <= page.head
            ):
                if journal_id is not None:
                    reset = True
                    offsets.clear()
                    draining.clear()
                    gone.clear()
                journal_id = page.journal_id
                position = max(page.floor, page.head - self._backlog)
                page = self._events.read_after(position, _BATCH_EVENTS)
            roster = await self._timed(
                roster_from_view(page.view if page is not None else None)
            )
            source = (
                "available" if page is not None and page.available else "unavailable"
            )
            if reset or sent != (roster, source):
                sent = (roster, source)
                yield RosterItem(roster, source, reset)
                reset = False
            if page is not None and page.events:
                position += len(page.events)
                more = len(page.events) >= _BATCH_EVENTS
                steps: list[Step] = []
                for event in page.events:
                    step = orchestration_step(event, roster)
                    if step is not None:
                        steps.append(step)
                for group in chunks(steps):
                    yield StepsItem(group)
            live = {entry.dispatch_id for entry in roster if entry.state in self._live}
            draining |= {key for key in offsets if key not in live and key not in gone}
            draining &= {entry.dispatch_id for entry in roster}
            for entry in followed(
                (entry for entry in roster if entry.dispatch_id not in gone),
                draining,
                self._live,
                self._cap,
            ):
                key = entry.dispatch_id
                try:
                    worker_page = await self._workers.read(key, offsets.get(key, 0))
                except WorkerNotFound:
                    # The ledger has no record yet or any more: read again on the next tick.
                    draining.discard(key)
                    continue
                offsets[key] = worker_page.offset
                for group in chunks(agent_steps(worker_page, entry, self._now())):
                    yield StepsItem(group)
                if worker_page.more:
                    more = True
                elif key in draining:
                    draining.discard(key)
                    gone.add(key)
            if not more:
                await self._sleep(self._poll)
