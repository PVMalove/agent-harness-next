"""The worker steps use case: a page of a dispatch's worker log by offset, and a stream of pages.

Observation only reads: the ledger records without its lock and the worker log. It never decides
or changes the dispatch, and the worker outcome never depends on it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

from ..domain.live_steps import (
    DispatchTiming,
    InProcessObservation,
    dispatch_timing,
    in_process_observation,
)
from ..domain.worker_steps import (
    STEP_BUDGET_BYTES,
    StepsPage,
    in_process,
    no_log_page,
    page_from_reading,
    select_source,
    worth_sending,
)
from .ports import CheckpointsReader, StepsLogReader, WorkerFactsReader

POLL_SECONDS = 1.0


class WorkerNotFound(LookupError):
    """The ledger has no dispatch with the requested id."""


class WorkerStepsQuery:
    """Reads one page off the event loop per call; holds no cursor between calls."""

    def __init__(
        self,
        repo: Path,
        *,
        facts: WorkerFactsReader,
        log: StepsLogReader,
        checkpoints: CheckpointsReader,
        budget: int = STEP_BUDGET_BYTES,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.repo = repo.resolve()
        self._facts = facts
        self._log = log
        self._checkpoints = checkpoints
        self._budget = budget
        self._poll = poll_seconds
        self._sleep = sleep

    async def timing(self, dispatch_id: str) -> DispatchTiming | None:
        """When the dispatch was created and its latest heartbeat or state change; None without a
        ledger record."""
        facts = await asyncio.to_thread(self._facts, self.repo, dispatch_id)
        return dispatch_timing(facts.dispatch, facts.status) if facts else None

    async def observation(self, dispatch_id: str) -> InProcessObservation | None:
        """The ledger facts of an in-process dispatch, which has no step log; None for another
        transport or without a ledger record."""
        facts = await asyncio.to_thread(self._facts, self.repo, dispatch_id)
        if facts is None or not in_process(facts):
            return None
        checkpoints = await asyncio.to_thread(self._checkpoints, self.repo, facts)
        return in_process_observation(facts.status, checkpoints)

    async def read(self, dispatch_id: str, offset: int) -> StepsPage:
        facts = await asyncio.to_thread(self._facts, self.repo, dispatch_id)
        if facts is None:
            raise WorkerNotFound(dispatch_id)
        source = select_source(facts)
        if source == "none":
            return no_log_page(dispatch_id, offset)
        reading = await asyncio.to_thread(
            self._log, self.repo, facts, source, offset, self._budget
        )
        return page_from_reading(dispatch_id, reading)

    async def follow(
        self, dispatch_id: str, offset: int
    ) -> AsyncGenerator[StepsPage, None]:
        """Pages with new steps, a reset or a changed state, until the consumer stops."""
        previous: StepsPage | None = None
        while True:
            page = await self.read(dispatch_id, offset)
            if worth_sending(previous, page):
                yield page
            previous, offset = page, page.offset
            if not page.more:
                await self._sleep(self._poll)
