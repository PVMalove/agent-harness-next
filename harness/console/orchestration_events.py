"""Live orchestration events for the console server's ``orchestration.subscribe`` stream.

A poller compares the orchestration source with the last view it read, about once per second,
and appends the differences as events with a monotonic ``seq``. The console only reads: the file
ledger is read without the ledger lock, like the Reports section reads it, and the ``audit/``
directory is never read. In the runtime-store epoch a poll first probes the store revision with an
empty ``state.read`` and reads the collections only when the revision moved.

Request: ``{id, type: "orchestration.subscribe", cursor?}``. Without a cursor the stream starts at
the head. Replies carry ``kind``: ``source`` (always first, then on every change of the source
state) or ``events`` (a non-empty batch with the cursor of its last event). A cursor is
``<journal>-<seq>``; a subscription with cursor ``c`` gets exactly the events with ``seq > c``, in
order. Events are served only after the console-owned journal (``event_journal.py``) has them on
disk, so a cursor survives a restart of the server; the first poll after a restart appends the
changes made while no server ran. Event types: ``batch.transition``, ``dispatch.transition``, ``gate.decision``, ``qa.run``
and ``qa.attempt``.

Standard library and harness only: nothing here imports ``h11`` or ``websockets``.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import (
    POINTER_NAME,
    JsonObject,
    LifecycleLedger,
    store_is_authority,
)

from .discovery import discovery_path
from .event_journal import Event, EventJournal, JournalUnavailable, View
from .json_fields import text
from .snapshots import (
    ID_BYTES,
    MAX_ID_CHARS,
    MESSAGE_BYTES,
    PROTOCOL_VERSION,
    Rejected,
    _clip,
    encode,
    error_reply,
    parse_envelope,
)

ORCHESTRATION_SUBSCRIBE = "orchestration.subscribe"
POLL_INTERVAL_SECONDS = 1.0
_BATCH_EVENTS = 32
_FIELDS = frozenset({"id", "type", "cursor"})
STORE_READ_TIMEOUT_SECONDS = 2
_STORE_COLLECTIONS = ("batches", "dispatch-status", "qa-lane")
JOURNAL_NAME = "orchestration-events.jsonl"
_JOURNAL_UNAVAILABLE = "journal_unavailable"
_JOURNAL_MESSAGE = "The console event journal cannot be read or written."
_EXPIRED = (
    "The cursor is older than the kept events: read the snapshot and subscribe again."
)


@dataclass(frozen=True)
class BatchFacts:
    ticket: str
    state: str
    # (dispatch_id, role, state of the batch entry), in the batch's order.
    dispatches: tuple[tuple[str, str, str], ...]
    decisions: tuple[JsonObject, ...]


@dataclass(frozen=True)
class Observation:
    """What one poll read from the orchestration source."""

    store: str
    batches: dict[str, BatchFacts] = field(default_factory=dict)
    dispatch_states: dict[str, str] = field(default_factory=dict)
    qa_outcomes: dict[str, str] = field(default_factory=dict)
    qa_attempts: dict[str, JsonObject] = field(default_factory=dict)


class SourceUnavailable(Exception):
    """The orchestration source cannot be read as a whole: ``reason`` is ``missing``,
    ``unreadable`` or ``runtime_unavailable``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason, self.message = reason, message


# ``state.read`` of the runtime store: the records by path and the store revision.
type StoreFetch = Callable[
    [Sequence[str], Sequence[str]], tuple[Mapping[str, object], int | None]
]


class OrchestrationReader(Protocol):
    """Runs in a thread and raises ``SourceUnavailable``."""

    def read(self) -> Observation: ...


def _list_records(directory: Path) -> list[Path]:
    try:
        return sorted(
            entry for entry in directory.iterdir() if entry.name.endswith(".json")
        )
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise SourceUnavailable(
            "unreadable", f"{directory.name}: {type(exc).__name__}"
        ) from exc


def _observation(
    store: str,
    batches: Mapping[str, JsonObject],
    statuses: Mapping[str, JsonObject],
    attempts: Mapping[str, JsonObject],
    outcome: Callable[[str], str | None],
) -> Observation:
    """The observation of one poll from the batch, dispatch-status and qa-lane attempt records;
    ``outcome`` reads the outcome of a reported QA dispatch."""
    facts: dict[str, BatchFacts] = {}
    for record in batches.values():
        batch_id = record.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            continue
        entries = record.get("dispatches")
        decisions = record.get("coordinator_decisions")
        facts[batch_id] = BatchFacts(
            ticket=text(record.get("ticket")),
            state=text(record.get("state")),
            dispatches=tuple(
                (
                    text(entry.get("dispatch_id")),
                    text(entry.get("role")),
                    text(entry.get("state")),
                )
                for entry in (entries if isinstance(entries, list) else [])
                if isinstance(entry, dict) and text(entry.get("dispatch_id"))
            ),
            decisions=tuple(
                entry
                for entry in (decisions if isinstance(decisions, list) else [])
                if isinstance(entry, dict)
            ),
        )
    dispatch_states = {
        text(record.get("dispatch_id")): text(record.get("state"))
        for record in statuses.values()
        if text(record.get("dispatch_id"))
    }
    qa_outcomes: dict[str, str] = {}
    for batch in facts.values():
        for dispatch_id, role, entry_state in batch.dispatches:
            state = dispatch_states.get(dispatch_id) or entry_state
            if role == "qa" and state == "reported":
                found = outcome(dispatch_id)
                if found is not None:
                    qa_outcomes[dispatch_id] = found
    return Observation(store, facts, dispatch_states, qa_outcomes, dict(attempts))


class ProjectReader:
    """Reads the project's orchestration state. Unchanged files are not read again: a record is
    cached by its file signature, and a record that cannot be read keeps its last value."""

    def __init__(self, repo: Path, *, store_fetch: StoreFetch | None = None) -> None:
        self.repo = repo
        self._store_fetch = store_fetch or self._runtime_fetch
        self._records: dict[Path, tuple[tuple[int, int, int], JsonObject]] = {}
        self._outcomes: dict[str, str] = {}
        self._store_revision: int | None = None
        self._store_view: Observation | None = None

    def _runtime_fetch(
        self, collections: Sequence[str], paths: Sequence[str]
    ) -> tuple[Mapping[str, object], int | None]:
        """``state.read`` of the runtime; the console never starts the runtime itself."""
        from harness.orchestration.runtime_client import (
            RuntimeClient,
            RuntimeClientError,
        )

        try:
            reply = RuntimeClient(self.repo).call(
                "state.read",
                operation_id=f"console.events-{uuid.uuid4().hex}",
                payload={"collections": list(collections), "paths": list(paths)},
                timeout_seconds=STORE_READ_TIMEOUT_SECONDS,
            )
        except RuntimeClientError as exc:
            reason = (
                "runtime_unavailable"
                if exc.code == "runtime_unavailable"
                else "unreadable"
            )
            raise SourceUnavailable(
                reason, f"The runtime store did not answer state.read ({exc.code})."
            ) from exc
        records = reply.result.get("records")
        return (records if isinstance(records, dict) else {}), reply.revision

    def _read_store(self) -> Observation:
        """One probe of the store revision; the collections are read only when it moved."""
        _, revision = self._store_fetch([], [])
        if (
            self._store_view is not None
            and revision is not None
            and revision == self._store_revision
        ):
            return self._store_view
        records, read_revision = self._store_fetch(_STORE_COLLECTIONS, [])

        def section(prefix: str) -> dict[str, JsonObject]:
            return {
                path: record
                for path, record in records.items()
                if path.startswith(prefix) and isinstance(record, dict)
            }

        def outcome(dispatch_id: str) -> str | None:
            if dispatch_id not in self._outcomes:
                path = f"reports/{dispatch_id}.json"
                report = self._store_fetch([], [path])[0].get(path)
                if not isinstance(report, dict):
                    return None
                self._outcomes[dispatch_id] = text(report.get("outcome"), "unknown")
            return self._outcomes[dispatch_id]

        observation = _observation(
            "runtime-store",
            section("batches/"),
            section("dispatch-status/"),
            section("qa-lane/attempts/"),
            outcome,
        )
        self._store_revision = read_revision if read_revision is not None else revision
        self._store_view = observation
        return observation

    def _directory(self, directory: Path) -> dict[str, JsonObject]:
        found: dict[str, JsonObject] = {}
        for path in _list_records(directory):
            try:
                info = path.stat()
            except FileNotFoundError:
                continue
            signature = (info.st_ino, info.st_mtime_ns, info.st_size)
            cached = self._records.get(path)
            if cached is not None and cached[0] == signature:
                found[path.name] = cached[1]
                continue
            record = LifecycleLedger.read_record_lenient(path)
            if record is not None:
                self._records[path] = (signature, record)
                found[path.name] = record
            elif cached is not None:
                # A record that is being rewritten keeps its last readable value.
                found[path.name] = cached[1]
        return found

    def _outcome(self, root: Path, dispatch_id: str) -> str | None:
        if dispatch_id not in self._outcomes:
            report = LifecycleLedger.read_record_lenient(
                root / "reports" / f"{dispatch_id}.json"
            )
            if report is None:
                return None
            # A report is immutable, so its outcome is read once.
            self._outcomes[dispatch_id] = text(report.get("outcome"), "unknown")
        return self._outcomes[dispatch_id]

    def read(self) -> Observation:
        state = self.repo / STATE_REL
        if not state.is_dir():
            raise SourceUnavailable(
                "missing", "The project has no orchestration ledger."
            )
        if store_is_authority(state):
            return self._read_store()
        root = LifecycleLedger(state).records_root_lenient()
        if root is None:
            if not (state / POINTER_NAME).exists():
                raise SourceUnavailable(
                    "missing", "The project has no orchestration ledger."
                )
            raise SourceUnavailable(
                "unreadable", "The ledger pointer or its generation is not readable."
            )
        return _observation(
            "ledger",
            self._directory(root / "batches"),
            self._directory(root / "dispatch-status"),
            {
                f"qa-lane/attempts/{name}": record
                for name, record in self._directory(
                    root / "qa-lane" / "attempts"
                ).items()
            },
            lambda dispatch_id: self._outcome(root, dispatch_id),
        )


def compact(observation: Observation) -> View:
    """The JSON view a later poll compares with: decisions are kept as their count only."""
    return {
        "store": observation.store,
        "batches": {
            batch_id: {
                "ticket": batch.ticket,
                "state": batch.state,
                "dispatches": [list(entry) for entry in batch.dispatches],
                "decisions": len(batch.decisions),
            }
            for batch_id, batch in observation.batches.items()
        },
        "dispatch_states": dict(observation.dispatch_states),
        "qa_outcomes": dict(observation.qa_outcomes),
        "qa_attempts": {path: 1 for path in observation.qa_attempts},
    }


def _map(view: View, name: str) -> dict[str, object]:
    value = view.get(name)
    return value if isinstance(value, dict) else {}


def _id(value: object) -> str | None:
    return _clip(value, ID_BYTES) if isinstance(value, str) and value else None


def diff(previous: View, current: Observation) -> list[Event]:
    """The events between the last view and this observation, in a deterministic order: per batch
    (by id) its transition, its dispatch transitions, its new gate decisions and its QA runs;
    then dispatches known only by their status record, then new QA attempts. Removed records
    give no event, and a shorter decision list only resets the count."""
    old_batches = _map(previous, "batches")
    old_states = _map(previous, "dispatch_states")
    events: list[Event] = []
    seen: set[str] = set()
    owner: dict[str, str] = {}

    def old_state(dispatch_id: str, old_entry_state: str | None) -> str | None:
        state = old_states.get(dispatch_id)
        return state if isinstance(state, str) and state else old_entry_state

    for batch_id in sorted(current.batches):
        batch = current.batches[batch_id]
        old = old_batches.get(batch_id)
        old = old if isinstance(old, dict) else None
        if old is None or old.get("state") != batch.state:
            events.append(
                {
                    "event": "batch.transition",
                    "batch_id": _id(batch_id),
                    "ticket": _id(batch.ticket),
                    "from": _id(old.get("state")) if old is not None else None,
                    "to": _id(batch.state),
                }
            )
        old_entries = {
            entry[0]: entry[2]
            for entry in (old or {}).get("dispatches", [])
            if isinstance(entry, list) and len(entry) == 3
        }
        qa_runs: list[Event] = []
        for dispatch_id, role, entry_state in batch.dispatches:
            seen.add(dispatch_id)
            owner[dispatch_id] = batch_id
            state = current.dispatch_states.get(dispatch_id) or entry_state
            before = old_state(dispatch_id, old_entries.get(dispatch_id))
            if before == state:
                continue
            events.append(
                {
                    "event": "dispatch.transition",
                    "batch_id": _id(batch_id),
                    "dispatch_id": _id(dispatch_id),
                    "role": _id(role),
                    "from": _id(before),
                    "to": _id(state),
                }
            )
            if role == "qa" and state == "reported":
                qa_runs.append(
                    {
                        "event": "qa.run",
                        "batch_id": _id(batch_id),
                        "dispatch_id": _id(dispatch_id),
                        "outcome": _id(current.qa_outcomes.get(dispatch_id, "unknown")),
                    }
                )
        known = (old or {}).get("decisions", 0)
        known = known if isinstance(known, int) else 0
        for decision in batch.decisions[known:]:
            events.append(
                {
                    "event": "gate.decision",
                    "batch_id": _id(batch_id),
                    "dispatch_id": _id(decision.get("dispatch_id")),
                    "decision": _id(decision.get("decision")),
                    "next_role": _id(decision.get("next_role")),
                    "approved_by": _id(decision.get("approved_by")),
                    "approved_at": _id(decision.get("approved_at")),
                }
            )
        events.extend(qa_runs)
    for dispatch_id in sorted(set(current.dispatch_states) - seen):
        state = current.dispatch_states[dispatch_id]
        before = old_state(dispatch_id, None)
        if before != state:
            events.append(
                {
                    "event": "dispatch.transition",
                    "batch_id": None,
                    "dispatch_id": _id(dispatch_id),
                    "role": None,
                    "from": _id(before),
                    "to": _id(state),
                }
            )
    old_attempts = _map(previous, "qa_attempts")
    for path in sorted(set(current.qa_attempts) - set(old_attempts)):
        attempt = current.qa_attempts[path]
        dispatch_id = text(attempt.get("dispatch_id"))
        events.append(
            {
                "event": "qa.attempt",
                "batch_id": _id(owner.get(dispatch_id)),
                "dispatch_id": _id(dispatch_id),
                "stage": _id(attempt.get("stage")),
                "failed_at": _id(attempt.get("failed_at")),
                "message": _clip(text(attempt.get("message")), MESSAGE_BYTES),
            }
        )
    return events


def _now() -> str:
    return datetime.now(UTC).isoformat()


class _Subscribe(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(code)
        self.code, self.message = code, message


def _parse_cursor(value: str) -> tuple[str, int] | None:
    journal, separator, seq = value.partition("-")
    if (
        not separator
        or len(journal) != 16
        or any(char not in "0123456789abcdef" for char in journal)
        or not seq.isascii()
        or not seq.isdigit()
        or len(seq) > 16
        or (len(seq) > 1 and seq.startswith("0"))
    ):
        return None
    return journal, int(seq)


class OrchestrationEvents:
    """Owns the poller, the event journal and the source state of one console server."""

    def __init__(
        self,
        repo: Path,
        *,
        reader: OrchestrationReader | None = None,
        interval: float = POLL_INTERVAL_SECONDS,
        journal_path: Path | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self._reader = reader or ProjectReader(self.repo)
        self._interval = interval
        self._journal_path = journal_path
        self._journal: EventJournal | None = None
        self._source: dict[str, object] = {
            "state": "unavailable",
            "store": None,
            "reason": None,
            "message": "",
            "since": _now(),
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
            "since": _now(),
        }
        self._notify()

    def _unavailable(self, reason: str, message: str) -> None:
        self._set_source("unavailable", None, reason, message)

    def _path(self) -> Path:
        if self._journal_path is None:
            self._journal_path = discovery_path(self.repo).with_name(JOURNAL_NAME)
        return self._journal_path

    async def _opened(self) -> EventJournal | None:
        """The loaded journal; a journal that cannot be loaded is tried again on the next poll."""
        if self._journal is None:
            try:
                path = await asyncio.to_thread(self._path)
                journal = EventJournal(path, str((self.repo / STATE_REL).resolve()))
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
            observed_at = _now()
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
        parsed = _parse_cursor(cursor) if isinstance(cursor, str) else None
        if parsed is not None and parsed[0] != journal.journal_id:
            raise _Subscribe("cursor_expired", _EXPIRED)
        if parsed is None or parsed[1] > journal.head:
            raise _Subscribe(
                "invalid_cursor", "The cursor is not a cursor of this stream."
            )
        if parsed[1] < journal.floor:
            raise _Subscribe("cursor_expired", _EXPIRED)
        return parsed[1]

    async def replies(self, raw: str) -> AsyncGenerator[str, None]:
        """Stream the source state and the events after the cursor until the connection ends.
        Never raises: every failure is an error reply that ends the stream."""
        try:
            body, request_id, kind = parse_envelope(raw)
        except Rejected as rejected:
            yield error_reply(rejected.code, rejected.id, rejected.type)
            return
        echoed = kind[:MAX_ID_CHARS]
        envelope = {"v": PROTOCOL_VERSION, "id": request_id, "type": echoed, "ok": True}
        try:
            if kind != ORCHESTRATION_SUBSCRIBE:
                raise _Subscribe("unknown_type")
            if set(body) - _FIELDS or not isinstance(body.get("cursor", ""), str):
                raise _Subscribe("bad_request")
            await self._started()
            sent_source: dict[str, object] | None = None
            while (journal := self._journal) is None:
                # Without the journal no cursor can be checked: only the source state is sent.
                next_change = self._next_change
                if self._source is not sent_source:
                    sent_source = self._source
                    yield encode(
                        {
                            **envelope,
                            "kind": "source",
                            "cursor": body.get("cursor"),
                            "source": sent_source,
                        }
                    )
                await next_change.wait()
            position = self._position(journal, body.get("cursor"))
            while True:
                next_change = self._next_change
                current = self._journal
                if current is not None and current is not journal:
                    if current.journal_id != journal.journal_id:
                        raise _Subscribe("cursor_expired", _EXPIRED)
                    journal = current
                if position < journal.floor:
                    raise _Subscribe("cursor_expired", _EXPIRED)
                if self._source is not sent_source:
                    sent_source = self._source
                    yield encode(
                        {
                            **envelope,
                            "kind": "source",
                            "cursor": f"{journal.journal_id}-{position}",
                            "source": sent_source,
                        }
                    )
                batch = journal.events_after(position, _BATCH_EVENTS)
                if batch:
                    position += len(batch)
                    yield encode(
                        {
                            **envelope,
                            "kind": "events",
                            "cursor": f"{journal.journal_id}-{position}",
                            "events": batch,
                        }
                    )
                    await asyncio.sleep(0)
                else:
                    await next_change.wait()
        except _Subscribe as rejected:
            yield error_reply(rejected.code, request_id, echoed, rejected.message)

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._journal is not None:
            self._drop(self._journal)


def is_orchestration_request(raw: str) -> bool:
    """True for a request of type ``orchestration.subscribe``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == ORCHESTRATION_SUBSCRIBE
