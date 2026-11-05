"""Live orchestration events: the poller of one console server and the subscriptions to it.

A poller compares the orchestration source with the last view it read, about once per second,
and appends the differences as events with a monotonic ``seq``. The console only reads: the file
ledger is read without the ledger lock, like the Reports section reads it, and the ``audit/``
directory is never read. In the runtime-store epoch a poll first probes the store revision with an
empty ``state.read`` and reads the collections only when the revision moved.

A subscription with cursor ``c`` gets exactly the events with ``seq > c``, in order, and the
source state first and on every change of it. Events are served only after the console-owned
journal has them on disk, so a cursor survives a restart of the server; the first poll after a
restart appends the changes made while no server ran. Event types: ``batch.transition``,
``dispatch.transition``, ``gate.decision``, ``qa.run`` and ``qa.attempt``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path

from ...kernel.protocol import MESSAGE_BYTES, _clip
from ..domain.events import Event, compact, diff, format_cursor, parse_cursor
from .ports import (
    EventJournal,
    JournalUnavailable,
    OpenJournal,
    OrchestrationReader,
    SourceUnavailable,
    WallClock,
)

POLL_INTERVAL_SECONDS = 1.0
_BATCH_EVENTS = 32
_JOURNAL_UNAVAILABLE = "journal_unavailable"
_JOURNAL_MESSAGE = "The console event journal cannot be read or written."
_EXPIRED = (
    "The cursor is older than the kept events: read the snapshot and subscribe again."
)


class SubscriptionRejected(Exception):
    """A subscription that cannot go on: ``code`` with its message, if it has its own."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(code)
        self.code, self.message = code, message


@dataclass(frozen=True)
class SourceItem:
    """The source state, sent first and on every change; ``cursor`` is the position of the
    subscription, or the requested cursor while no journal is loaded."""

    cursor: str | None
    source: dict[str, object]


@dataclass(frozen=True)
class EventsItem:
    """A non-empty batch of events with the cursor of its last event."""

    cursor: str
    events: list[Event]


class OrchestrationEvents:
    """Owns the poller, the event journal and the source state of one console server."""

    def __init__(
        self,
        repo: Path,
        *,
        reader: OrchestrationReader,
        open_journal: OpenJournal,
        now: WallClock,
        interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self.repo = repo.resolve()
        self._reader = reader
        self._open_journal = open_journal
        self._now = now
        self._interval = interval
        self._journal: EventJournal | None = None
        self._source: dict[str, object] = {
            "state": "unavailable",
            "store": None,
            "reason": None,
            "message": "",
            "since": now(),
        }
        self._task: asyncio.Task[None] | None = None
        self._first_poll = asyncio.Event()
        self._next_change = asyncio.Event()

    def _notify(self) -> None:
        previous, self._next_change = self._next_change, asyncio.Event()
        previous.set()

    def _set_source(
        self,
        state: str,
        store: str | None,
        reason: str | None = None,
        message: str = "",
    ) -> None:
        """Record the source state; subscribers get a ``source`` message when it changed."""
        current = (self._source["state"], self._source["store"], self._source["reason"])
        if current == (state, store, reason):
            return
        self._source = {
            "state": state,
            "store": store,
            "reason": reason,
            "message": _clip(message, MESSAGE_BYTES),
            "since": self._now(),
        }
        self._notify()

    def _unavailable(self, reason: str, message: str) -> None:
        self._set_source("unavailable", None, reason, message)

    async def _opened(self) -> EventJournal | None:
        """The loaded journal; a journal that cannot be loaded is tried again on the next poll."""
        if self._journal is None:
            try:
                journal = await asyncio.to_thread(self._open_journal)
                await asyncio.to_thread(journal.load)
            except (JournalUnavailable, OSError, ValueError) as exc:
                detail = (
                    exc if isinstance(exc, JournalUnavailable) else type(exc).__name__
                )
                self._unavailable(
                    _JOURNAL_UNAVAILABLE, f"{_JOURNAL_MESSAGE} ({detail})"
                )
                return None
            self._journal = journal
            self._notify()
        return self._journal

    async def _poll(self) -> None:
        journal = await self._opened()
        if journal is None:
            return
        try:
            observation = await asyncio.to_thread(self._reader.read)
        except SourceUnavailable as exc:
            # The view stays at the last readable state: once the source is readable again, the
            # changes made meanwhile are delivered as events.
            self._unavailable(exc.reason, exc.message)
            return
        except Exception as exc:
            self._unavailable("unreadable", type(exc).__name__)
            return
        try:
            view = compact(observation)
            observed_at = self._now()
            events = [
                {"seq": journal.head + offset, "observed_at": observed_at, **event}
                for offset, event in enumerate(
                    diff(journal.view, observation) if journal.view is not None else [],
                    start=1,
                )
            ]
            line = journal.record(events, view)
        except Exception as exc:
            # Nothing was written: the view stays at the last persisted state.
            self._unavailable("unreadable", type(exc).__name__)
            return
        if line is not None:
            try:
                await asyncio.to_thread(journal.write, line)
            except JournalUnavailable as exc:
                # The view stays where it was, so the next poll writes the same events again.
                self._drop(journal)
                self._unavailable(_JOURNAL_UNAVAILABLE, f"{_JOURNAL_MESSAGE} ({exc})")
                return
            journal.accept(events, view)
            if journal.needs_compaction():
                try:
                    await asyncio.to_thread(journal.rewrite, journal.checkpoint())
                    journal.compacted()
                except JournalUnavailable:
                    # The records are on disk already; a broken file is reloaded from it.
                    self._drop(journal)
        self._set_source("available", observation.store)
        self._notify()

    def _drop(self, journal: EventJournal) -> None:
        journal.close()
        if self._journal is journal:
            self._journal = None

    async def _run(self) -> None:
        while True:
            try:
                await self._poll()
            except Exception as exc:
                # The poller never dies: an unexpected failure is a typed source state.
                self._unavailable("unreadable", type(exc).__name__)
            self._first_poll.set()
            await asyncio.sleep(self._interval)

    async def _started(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        await self._first_poll.wait()

    @staticmethod
    def _position(journal: EventJournal, cursor: object) -> int:
        if cursor is None:
            return journal.head
        parsed = parse_cursor(cursor) if isinstance(cursor, str) else None
        if parsed is not None and parsed[0] != journal.journal_id:
            raise SubscriptionRejected("cursor_expired", _EXPIRED)
        if parsed is None or parsed[1] > journal.head:
            raise SubscriptionRejected(
                "invalid_cursor", "The cursor is not a cursor of this stream."
            )
        if parsed[1] < journal.floor:
            raise SubscriptionRejected("cursor_expired", _EXPIRED)
        return parsed[1]

    async def subscribe(
        self, cursor: str | None
    ) -> AsyncGenerator[SourceItem | EventsItem, None]:
        """The source state and the events after `cursor` (the head without one) until the
        subscriber stops; a cursor that cannot go on is `SubscriptionRejected`."""
        await self._started()
        sent_source: dict[str, object] | None = None
        while (journal := self._journal) is None:
            # Without the journal no cursor can be checked: only the source state is sent.
            next_change = self._next_change
            if self._source is not sent_source:
                sent_source = self._source
                yield SourceItem(cursor, sent_source)
            await next_change.wait()
        position = self._position(journal, cursor)
        while True:
            next_change = self._next_change
            current = self._journal
            if current is not None and current is not journal:
                if current.journal_id != journal.journal_id:
                    raise SubscriptionRejected("cursor_expired", _EXPIRED)
                journal = current
            if position < journal.floor:
                raise SubscriptionRejected("cursor_expired", _EXPIRED)
            if self._source is not sent_source:
                sent_source = self._source
                yield SourceItem(
                    format_cursor(journal.journal_id, position), sent_source
                )
            batch = journal.events_after(position, _BATCH_EVENTS)
            if batch:
                position += len(batch)
                yield EventsItem(format_cursor(journal.journal_id, position), batch)
                await asyncio.sleep(0)
            else:
                await next_change.wait()

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._journal is not None:
            self._drop(self._journal)
