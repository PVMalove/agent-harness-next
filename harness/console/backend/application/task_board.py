"""The task-board snapshot: the open specs and the board of one spec, collected off the event loop
from the tracker and the ledger, cached per key for a TTL and, while the tracker is unavailable,
served from the last good payload with its age and the reason. Only reads, never writes."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from ..domain.task_board import (
    BOARD_TTL_SECONDS,
    BODY_READ_BYTES,
    KEPT_BOARDS,
    NO_TEMPLATE,
    PROMPT_TEMPLATE_PATH,
    BatchStage,
    PromptTemplate,
    SpecTickets,
    TrackerSpec,
    batch_stages,
    build_board_payload,
    build_specs_payload,
    parse_prompt_template,
)
from .ports import Clock, LedgerCollector, TaskBoardReader, TrackerUnavailable

Payload = dict[str, object]
_SPECS_KEY = ("specs", "")


@dataclass(frozen=True)
class BoardServed:
    """A served payload, whether it came from the cache, its age (None when there is no data)
    and, when the tracker could not be read, the reason and message."""

    payload: Payload
    cached: bool
    age_seconds: float | None
    stale: dict[str, str] | None


@dataclass
class _Entry:
    value: Payload | None = None
    stamp: float = 0.0
    failure: dict[str, str] | None = None
    failure_at: float = 0.0


class TaskBoardService:
    """Serves the task-board snapshots of one project."""

    def __init__(
        self,
        repo: Path,
        *,
        ttl: float = BOARD_TTL_SECONDS,
        clock: Clock,
        reader: TaskBoardReader,
        ledger: LedgerCollector,
    ) -> None:
        self._repo = repo
        self._ttl = ttl
        self._clock = clock
        self._reader = reader
        self._ledger = ledger
        self._entries: OrderedDict[tuple[str, str], _Entry] = OrderedDict()
        self._building: dict[tuple[str, str], asyncio.Task[BoardServed]] = {}

    def _served(
        self,
        value: Payload,
        cached: bool,
        age: float | None,
        stale: dict[str, str] | None,
    ) -> BoardServed:
        age = None if age is None else round(age, 3)
        return BoardServed(
            {**value, "stale": stale, "age_seconds": age}, cached, age, stale
        )

    def _cached(self, key: tuple[str, str]) -> BoardServed | None:
        entry = self._entries.get(key)
        if entry is None or entry.value is None:
            return None
        now = self._clock()
        if now - entry.stamp < self._ttl:
            return self._served(entry.value, True, now - entry.stamp, None)
        if entry.failure is not None and now - entry.failure_at < self._ttl:
            return self._served(entry.value, True, now - entry.stamp, entry.failure)
        return None

    def _store(self, key: tuple[str, str]) -> _Entry:
        entry = self._entries.setdefault(key, _Entry())
        self._entries.move_to_end(key)
        boards = [known for known in self._entries if known != _SPECS_KEY]
        for old in boards[: max(0, len(boards) - KEPT_BOARDS)]:
            del self._entries[old]
        return entry

    async def _build(
        self,
        key: tuple[str, str],
        collect: Callable[[], Payload],
        empty: Callable[[], Payload],
    ) -> BoardServed:
        try:
            value = await asyncio.to_thread(collect)
        except TrackerUnavailable as failure:
            now = self._clock()
            stale = {"reason": failure.reason, "message": failure.message}
            known = self._entries.get(key)
            if known is None or known.value is None:
                # A key without a good payload is not kept: it would evict good boards.
                return self._served(empty(), False, None, stale)
            self._store(key)
            known.failure, known.failure_at = stale, now
            return self._served(known.value, True, now - known.stamp, stale)
        finally:
            self._building.pop(key, None)
        entry = self._store(key)
        entry.value, entry.stamp, entry.failure = value, self._clock(), None
        return self._served(value, False, 0.0, None)

    async def _get(
        self,
        key: tuple[str, str],
        collect: Callable[[], Payload],
        empty: Callable[[], Payload],
        force: bool,
    ) -> BoardServed:
        task = self._building.get(key)
        if task is not None and force:
            # The collect under way may have read the tracker before this request: wait for it,
            # then join the collect started after it or start one.
            await asyncio.wait({task})
            task = self._building.get(key)
        if task is None:
            if not force and (cached := self._cached(key)) is not None:
                self._entries.move_to_end(key)
                return cached
            task = asyncio.create_task(self._build(key, collect, empty))
            task.add_done_callback(lambda done: done.cancelled() or done.exception())
            self._building[key] = task
        await asyncio.wait({task})
        return task.result()

    async def specs(self, force: bool = False) -> BoardServed:
        """The open specs of the project's tracker."""

        def collect() -> Payload:
            kind = self._reader.tracker_type(self._repo)
            return build_specs_payload(kind, self._reader.specs(self._repo))

        return await self._get(
            _SPECS_KEY, collect, lambda: build_specs_payload("", ()), force
        )

    def _stages(self) -> tuple[dict[str, BatchStage], bool]:
        try:
            view = self._ledger(self._repo)
        except Exception:  # a ledger failure never hides the tracker board
            return {}, False
        if view.unavailable:
            return {}, False
        return dict(batch_stages(view)), True

    def _template(self) -> PromptTemplate:
        """The project's prompt blocks, read again with every board; none without the file."""
        try:
            with (self._repo / PROMPT_TEMPLATE_PATH).open("rb") as handle:
                raw = handle.read(BODY_READ_BYTES)
        except OSError:
            return NO_TEMPLATE
        return parse_prompt_template(raw.decode("utf-8", "replace"))

    async def board(self, spec: str, force: bool = False) -> BoardServed:
        """The board of one spec; `SpecNotFound` when the tracker has no such spec."""

        def collect() -> Payload:
            kind = self._reader.tracker_type(self._repo)
            # The ledger stages do not depend on the tracker: read both at once.
            with ThreadPoolExecutor(max_workers=1) as pool:
                ledger = pool.submit(self._stages)
                tickets = self._reader.board(self._repo, spec)
                stages, ledger_ok = ledger.result()
            return build_board_payload(
                kind, tickets, stages, ledger_ok, template=self._template()
            )

        def empty() -> Payload:
            stub = TrackerSpec(spec, None, "", None, "", None, None)
            return build_board_payload("", SpecTickets(stub, (), {}), {}, False)

        return await self._get(("board", spec), collect, empty, force)
