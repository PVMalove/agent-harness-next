"""The screen snapshots of Reports, Orchestration, Recovery and Container route: collect them off
the event loop, keep the ledger and the batch history in a short single-flight cache and hand out
every snapshot as the first page of its JSON text, kept for `snapshot.page`."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from ...kernel.batch_history import History
from ...kernel.reports import LedgerView, ledger_payload, timeline_payload
from ..domain.snapshots import HOME_TTL_SECONDS, TextPages
from .ports import Clock, LedgerCollector, LockReader, RecoveryReader, RouteReader
from .task_board import TaskBoardService

T = TypeVar("T")


class NotFound(LookupError):
    """The ledger has no report or batch with the requested id."""


@dataclass(frozen=True)
class Paged:
    """The first page of a snapshot's JSON text, the id its other pages are read under and, for
    a cached source, whether it came from the cache and how old it is."""

    snapshot_id: int
    text: str
    next: int
    done: bool
    cached: bool = False
    age_seconds: float = 0.0


@dataclass(frozen=True)
class _Ledger:
    view: LedgerView
    payload: dict[str, object]


class _Source(Generic[T]):
    """One cached value: fresh for the TTL, rebuilt one collect at a time off the loop. The value
    is released when its TTL expires and before every rebuild, so at most one is ever held. A
    failed collect raises and leaves the cache empty; a cancelled waiter never cancels a collect."""

    def __init__(self, ttl: float, clock: Clock) -> None:
        self._ttl = ttl
        self._clock = clock
        self._value: T | None = None
        self._stamp = 0.0
        self._generation = 0
        self._building: asyncio.Task[tuple[T, bool, float]] | None = None

    def _fresh(self) -> tuple[T, bool, float] | None:
        if self._value is None:
            return None
        age = self._clock() - self._stamp
        if age < self._ttl:
            return self._value, True, age
        self._value = None
        return None

    def _release(self, generation: int) -> None:
        if self._generation == generation:
            self._value = None

    async def _rebuild(self, collect: Callable[[], T]) -> tuple[T, bool, float]:
        self._value = None
        try:
            value = await asyncio.to_thread(collect)
            self._value, self._stamp = value, self._clock()
            self._generation += 1
            asyncio.get_running_loop().call_later(
                self._ttl, self._release, self._generation
            )
            return value, False, 0.0
        finally:
            self._building = None

    async def get(
        self, collect: Callable[[], T], *, force: bool = False
    ) -> tuple[T, bool, float]:
        """The value with whether it was cached and its age."""
        while True:
            if not force and (fresh := self._fresh()) is not None:
                return fresh
            if self._building is None:
                break
            await asyncio.wait({self._building})
        task = self._building = asyncio.create_task(self._rebuild(collect))
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        await asyncio.wait({task})
        return task.result()


def snapshot_text(payload: object) -> str:
    """The canonical JSON text of a snapshot payload, as the pages carry it."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _ledger(view: LedgerView) -> _Ledger:
    return _Ledger(view, ledger_payload(view))


class ScreenService:
    """Serves the screen snapshots of one project."""

    def __init__(
        self,
        repo: Path,
        *,
        ttl: float = HOME_TTL_SECONDS,
        clock: Clock,
        ledger: LedgerCollector,
        ledger_online: LedgerCollector,
        lock: LockReader,
        recovery: RecoveryReader,
        route: RouteReader,
        board: TaskBoardService | None = None,
    ) -> None:
        self._repo = repo
        self._collect_ledger = ledger
        self._collect_online = ledger_online
        self._read_lock = lock
        self._recovery = recovery
        self._route = route
        self._board = board
        self._ledger: _Source[_Ledger] = _Source(ttl, clock)
        self._history: _Source[History] = _Source(ttl, clock)
        self._pages = TextPages()

    async def _paged(
        self, payload: object, cached: bool = False, age: float = 0.0
    ) -> Paged:
        text = await asyncio.to_thread(snapshot_text, payload)
        snapshot_id = self._pages.keep(text)
        page, next_offset, done = self._pages.page(snapshot_id, 0)
        return Paged(snapshot_id, page, next_offset, done, cached, round(age, 3))

    async def _cached_ledger(self, force: bool) -> tuple[_Ledger, bool, float]:
        return await self._ledger.get(
            lambda: _ledger(self._collect_ledger(self._repo)), force=force
        )

    async def reports(self, *, force: bool = False, online: bool = False) -> Paged:
        """The ledger without report bodies; `online` adds the PR timings, always rebuilt and
        never cached."""
        if online:
            found = await asyncio.to_thread(
                lambda: _ledger(self._collect_online(self._repo))
            )
            return await self._paged(found.payload)
        ledger, cached, age = await self._cached_ledger(force)
        return await self._paged(ledger.payload, cached, age)

    async def report(self, dispatch_id: str) -> Paged:
        """The whole body of one completion report; `NotFound` when the ledger has none."""
        ledger, _, _ = await self._cached_ledger(False)
        for entry in ledger.view.reports:
            if entry.dispatch_id == dispatch_id:
                return await self._paged(entry.report)
        raise NotFound(dispatch_id)

    async def timeline(self, batch_id: str) -> Paged:
        """The chronology of one batch; `NotFound` when the ledger has no such batch."""
        ledger, _, _ = await self._cached_ledger(False)
        timeline = await asyncio.to_thread(ledger.view.timeline, batch_id)
        if timeline is None:
            raise NotFound(batch_id)
        return await self._paged(timeline_payload(timeline))

    async def lock(self) -> dict[str, object]:
        """The ledger lock state, or the text of why it cannot be read."""
        try:
            state = await asyncio.to_thread(self._read_lock, self._repo)
        except Exception as exc:  # shown to the operator, never hidden
            return {"lock": None, "error": str(exc) or type(exc).__name__}
        return {"lock": state, "error": None}

    async def orchestration(self, *, force: bool = False) -> Paged:
        """The ledger of the Orchestration screen with the ledger lock state."""
        ledger, cached, age = await self._cached_ledger(force)
        lock = await self.lock()
        return await self._paged({"ledger": ledger.payload, "lock": lock}, cached, age)

    async def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> Paged:
        """The batch history and, for a selected batch, its `recovery status`."""
        history, cached, age = await self._history.get(
            lambda: self._recovery.history(self._repo), force=force
        )
        status = (
            await asyncio.to_thread(self._recovery.status, self._repo, batch, skip)
            if batch
            else None
        )
        return await self._paged(
            {
                "history": history.to_payload(),
                "status": status.to_payload() if status is not None else None,
            },
            cached,
            age,
        )

    async def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> Paged:
        """The authored configuration and, for a selected batch, its `dispatch preflight`."""
        authored = await asyncio.to_thread(self._route.authored, self._repo)
        preflight = (
            await asyncio.to_thread(
                self._route.preflight, self._repo, batch, role, runtime
            )
            if batch
            else None
        )
        return await self._paged(
            {
                "authored": authored.to_payload(),
                "preflight": preflight.to_payload() if preflight is not None else None,
            }
        )

    async def task_board_specs(self, *, force: bool = False) -> Paged:
        """The open specs of the task board; `NotFound` without a configured board."""
        if self._board is None:
            raise NotFound("task_board")
        served = await self._board.specs(force)
        return await self._paged(served.payload, served.cached, served.age_seconds or 0.0)

    async def task_board(self, spec: str, *, force: bool = False) -> Paged:
        """The task board of one spec; `SpecNotFound` when the tracker has no such spec."""
        if self._board is None:
            raise NotFound("task_board")
        served = await self._board.board(spec, force)
        return await self._paged(served.payload, served.cached, served.age_seconds or 0.0)

    def page(self, snapshot_id: int, offset: int) -> tuple[str, int, bool]:
        """A further page of a kept snapshot; `LookupError` when it is no longer kept,
        `ValueError` for an offset beyond its text."""
        return self._pages.page(snapshot_id, offset)
