"""The worker steps use case: a page of a dispatch's worker log by offset, and a stream of pages.

Observation only reads: the ledger records without its lock and the worker log. It never decides
or changes the dispatch, and the worker outcome never depends on it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

from ..domain.worker_steps import (
    STEP_BUDGET_BYTES,
    StepsPage,
    no_log_page,
    page_from_reading,
    select_source,
    worth_sending,
)
from .ports import StepsLogReader, WorkerFactsReader

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
        budget: int = STEP_BUDGET_BYTES,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.repo = repo.resolve()
        self._facts = facts
        self._log = log
        self._budget = budget
        self._poll = poll_seconds
        self._sleep = sleep

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
