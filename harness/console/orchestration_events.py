"""Live orchestration events for the console server's ``orchestration.subscribe`` stream.

A poller compares the orchestration source with the last view it read, about once per second,
and appends the differences as events with a monotonic ``seq``. The console only reads: the file
ledger is read without the ledger lock, like the Reports section reads it, and the ``audit/``
directory is never read.

Request: ``{id, type: "orchestration.subscribe", cursor?}``. Without a cursor the stream starts at
the head. Replies carry ``kind``: ``source`` (always first, then on every change of the source
state) or ``events`` (a non-empty batch with the cursor of its last event). A cursor is
``<journal>-<seq>``; a subscription with cursor ``c`` gets exactly the events with ``seq > c``, in
order. Event types: ``batch.transition``, ``dispatch.transition``, ``gate.decision``, ``qa.run``
and ``qa.attempt``.

Standard library and harness only: nothing here imports ``h11`` or ``websockets``.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncGenerator, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import JsonObject, LifecycleLedger

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

type View = dict[str, object]
type Event = dict[str, object]


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


class OrchestrationReader(Protocol):
    def read(self) -> Observation: ...


def _list_records(directory: Path) -> list[Path]:
    try:
        return sorted(
            entry for entry in directory.iterdir() if entry.name.endswith(".json")
        )
    except FileNotFoundError:
        return []


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

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self._records: dict[Path, tuple[tuple[int, int, int], JsonObject]] = {}
        self._outcomes: dict[str, str] = {}

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
        root = LifecycleLedger(self.repo / STATE_REL).records_root_lenient()
        if root is None:
            raise OSError("the orchestration ledger is not readable")
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
    """Owns the poller, the event sequence and the source state of one console server."""

    def __init__(
        self,
        repo: Path,
        *,
        reader: OrchestrationReader | None = None,
        interval: float = POLL_INTERVAL_SECONDS,
    ) -> None:
        self.repo = repo.resolve()
        self._reader = reader or ProjectReader(self.repo)
        self._interval = interval
        self._journal = secrets.token_hex(8)
        self._events: list[Event] = []
        self._view: View | None = None
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

    @property
    def head(self) -> int:
        return int(self._events[-1]["seq"]) if self._events else 0  # type: ignore[call-overload]

    def _notify(self) -> None:
        previous, self._next_change = self._next_change, asyncio.Event()
        previous.set()

    def _set_source(self, state: str, store: str | None) -> None:
        if (self._source["state"], self._source["store"]) == (state, store):
            return
        self._source = {
            "state": state,
            "store": store,
            "reason": None,
            "message": "",
            "since": _now(),
        }
        self._notify()

    async def _poll(self) -> None:
        try:
            observation = await asyncio.to_thread(self._reader.read)
        except Exception:
            return
        view = compact(observation)
        if self._view is not None:
            observed_at = _now()
            for event in diff(self._view, observation):
                self._events.append(
                    {"seq": self.head + 1, "observed_at": observed_at, **event}
                )
        self._view = view
        self._set_source("available", observation.store)
        self._notify()

    async def _run(self) -> None:
        while True:
            await self._poll()
            self._first_poll.set()
            await asyncio.sleep(self._interval)

    async def _started(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())
        await self._first_poll.wait()

    def _position(self, body: Mapping[str, object]) -> int:
        cursor = body.get("cursor")
        if cursor is None:
            return self.head
        if not isinstance(cursor, str):
            raise _Subscribe("bad_request")
        parsed = _parse_cursor(cursor)
        if parsed is None or parsed[1] > self.head:
            raise _Subscribe(
                "invalid_cursor", "The cursor is not a cursor of this stream."
            )
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
            position = self._position(body)
            sent_source: dict[str, object] | None = None
            while True:
                next_change = self._next_change
                if self._source is not sent_source:
                    sent_source = self._source
                    yield encode(
                        {
                            **envelope,
                            "kind": "source",
                            "cursor": f"{self._journal}-{position}",
                            "source": sent_source,
                        }
                    )
                batch = self._events[position : position + _BATCH_EVENTS]
                if batch:
                    position = int(batch[-1]["seq"])  # type: ignore[call-overload]
                    yield encode(
                        {
                            **envelope,
                            "kind": "events",
                            "cursor": f"{self._journal}-{position}",
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


def is_orchestration_request(raw: str) -> bool:
    """True for a request of type ``orchestration.subscribe``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == ORCHESTRATION_SUBSCRIBE
