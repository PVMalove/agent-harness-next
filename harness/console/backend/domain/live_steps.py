"""The live step list of the web console: the dispatches it follows and the items it shows.

One list merges two observed sources: the orchestration events of the console journal and the
worker steps of the dispatches that are live. Only allowlisted fields reach a client: the event
fields of `domain/events.py` and the kind and text of a worker step, which the worker log reader
already cut to text and tool names. Pure: the caller reads the journal and the logs.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ...kernel.json_fields import text
from ...kernel.protocol import ID_BYTES, MESSAGE_BYTES, _clip
from .worker_steps import StepsPage

ORCHESTRATION_EVENTS = (
    "batch.transition",
    "dispatch.transition",
    "gate.decision",
    "qa.run",
    "qa.attempt",
)
# Step items in one reply: with the envelope the reply stays below `MESSAGE_LIMIT`.
REPLY_BUDGET_BYTES = 48 * 1024
# A live dispatch without a heartbeat or state change for this long is silent: two heartbeat
# intervals of the worker contract.
SILENT_AFTER_SECONDS = 600


@dataclass(frozen=True)
class RosterDispatch:
    """A dispatch of a batch in the journal view, with its current state."""

    dispatch_id: str
    batch_id: str
    ticket: str
    role: str
    state: str
    batch_state: str = ""
    branch: str = ""
    # Read for a live dispatch only: when it was created, its latest heartbeat or state change,
    # and whether that is older than `SILENT_AFTER_SECONDS`; "" and False otherwise.
    started_at: str = ""
    last_event_at: str = ""
    silent: bool = False

    def to_wire(self) -> dict[str, object]:
        return {
            "dispatch_id": self.dispatch_id,
            "batch_id": self.batch_id,
            "ticket": self.ticket,
            "role": self.role,
            "state": self.state,
            "batch_state": self.batch_state,
            "branch": self.branch,
            "started_at": self.started_at,
            "last_event_at": self.last_event_at,
            "silent": self.silent,
        }


@dataclass(frozen=True)
class DispatchTiming:
    """When a dispatch was created and its latest heartbeat or state change; "" when unknown."""

    started_at: str
    last_event_at: str


def _moment(value: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def dispatch_timing(
    dispatch: Mapping[str, object], status: Mapping[str, object] | None
) -> DispatchTiming:
    """The timing of a dispatch from its record and status record."""
    found = status or {}
    moments = [
        (moment, value)
        for value in (text(found.get("heartbeat_at")), text(found.get("updated_at")))
        if value and (moment := _moment(value)) is not None
    ]
    return DispatchTiming(
        started_at=_clip(text(dispatch.get("created_at")), ID_BYTES),
        last_event_at=_clip(max(moments)[1], ID_BYTES) if moments else "",
    )


def timed(entry: RosterDispatch, timing: DispatchTiming | None, now: str) -> RosterDispatch:
    """`entry` with its timing and whether it is silent at `now`."""
    if timing is None:
        return entry
    last, current = _moment(timing.last_event_at), _moment(now)
    since = _moment(timing.started_at) if last is None else last
    silent = (
        since is not None
        and current is not None
        and (current - since).total_seconds() > SILENT_AFTER_SECONDS
    )
    return replace(
        entry,
        started_at=timing.started_at,
        last_event_at=timing.last_event_at,
        silent=silent,
    )


def _id(value: object) -> str | None:
    return _clip(value, ID_BYTES) if isinstance(value, str) and value else None


def roster_from_view(view: Mapping[str, object] | None) -> tuple[RosterDispatch, ...]:
    """The dispatches of the compact journal view, batches by id and dispatches in batch order;
    the state of a dispatch's status record wins over the state of its batch entry."""
    if view is None:
        return ()
    batches = view.get("batches")
    states = view.get("dispatch_states")
    batches = batches if isinstance(batches, dict) else {}
    states = states if isinstance(states, dict) else {}
    roster: list[RosterDispatch] = []
    seen: set[str] = set()
    for batch_id in sorted(batches):
        batch = batches[batch_id]
        if not isinstance(batch, dict) or not _id(batch_id):
            continue
        entries = batch.get("dispatches")
        for entry in entries if isinstance(entries, list) else []:
            if not isinstance(entry, list) or len(entry) != 3:
                continue
            dispatch_id, role, entry_state = (_id(item) for item in entry)
            if dispatch_id is None or dispatch_id in seen:
                continue
            seen.add(dispatch_id)
            roster.append(
                RosterDispatch(
                    dispatch_id=dispatch_id,
                    batch_id=_clip(batch_id, ID_BYTES),
                    ticket=_id(batch.get("ticket")) or "",
                    role=role or "",
                    state=_id(states.get(dispatch_id)) or entry_state or "",
                    batch_state=_id(batch.get("state")) or "",
                    branch=_id(batch.get("branch")) or "",
                )
            )
    return tuple(roster)


@dataclass(frozen=True)
class AgentStep:
    """One visible worker step: its kind and text, never thinking, tool inputs or raw JSON."""

    dispatch_id: str
    batch_id: str
    role: str
    source: str
    structure: str
    kind: str
    text: str
    observed_at: str

    def to_wire(self) -> dict[str, object]:
        return {
            "origin": "agent",
            "dispatch_id": self.dispatch_id,
            "batch_id": self.batch_id,
            "role": self.role,
            "source": self.source,
            "structure": self.structure,
            "kind": self.kind,
            "text": self.text,
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True)
class OrchestrationStep:
    """One orchestration event with the fields its text needs; ``role`` and ``ticket`` come from
    the roster when the event itself has none."""

    seq: int
    observed_at: str
    event: str
    batch_id: str | None
    dispatch_id: str | None
    ticket: str | None
    role: str | None
    from_state: str | None
    to_state: str | None
    decision: str | None
    next_role: str | None
    outcome: str | None
    stage: str | None
    message: str

    def to_wire(self) -> dict[str, object]:
        return {
            "origin": "orchestration",
            "seq": self.seq,
            "observed_at": self.observed_at,
            "event": self.event,
            "batch_id": self.batch_id,
            "dispatch_id": self.dispatch_id,
            "ticket": self.ticket,
            "role": self.role,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "decision": self.decision,
            "next_role": self.next_role,
            "outcome": self.outcome,
            "stage": self.stage,
            "message": self.message,
        }


type Step = AgentStep | OrchestrationStep


def orchestration_step(
    event: Mapping[str, object], roster: Iterable[RosterDispatch]
) -> OrchestrationStep | None:
    """The step of one journal event; an event of an unknown type gives none."""
    kind = event.get("event")
    seq = event.get("seq")
    if kind not in ORCHESTRATION_EVENTS or not isinstance(seq, int):
        return None
    dispatches = {entry.dispatch_id: entry for entry in roster}
    tickets = {entry.batch_id: entry.ticket for entry in dispatches.values()}
    dispatch_id = _id(event.get("dispatch_id"))
    known = dispatches.get(dispatch_id) if dispatch_id else None
    batch_id = _id(event.get("batch_id")) or (known.batch_id if known else None)
    role = _id(event.get("role")) or (known.role if known else None)
    ticket = _id(event.get("ticket")) or (tickets.get(batch_id) if batch_id else None)
    return OrchestrationStep(
        seq=seq,
        observed_at=_id(event.get("observed_at")) or "",
        event=str(kind),
        batch_id=batch_id,
        dispatch_id=dispatch_id,
        ticket=ticket or None,
        role=None if kind == "batch.transition" else role,
        from_state=_id(event.get("from")),
        to_state=_id(event.get("to")),
        decision=_id(event.get("decision")),
        next_role=_id(event.get("next_role")),
        outcome=_id(event.get("outcome")),
        stage=_id(event.get("stage")),
        message=_clip(text(event.get("message")), MESSAGE_BYTES),
    )


def agent_steps(
    page: StepsPage, entry: RosterDispatch, observed_at: str
) -> tuple[AgentStep, ...]:
    """The visible steps of one worker log page; a page without a log has none."""
    if page.source not in ("structured", "plain"):
        return ()
    return tuple(
        AgentStep(
            dispatch_id=entry.dispatch_id,
            batch_id=entry.batch_id,
            role=entry.role,
            source=page.source,
            structure=page.structure,
            kind=step.kind,
            text=step.text,
            observed_at=observed_at,
        )
        for step in page.steps
    )


def followed(
    roster: Iterable[RosterDispatch],
    draining: Collection[str],
    live_states: Collection[str],
    cap: int,
) -> tuple[RosterDispatch, ...]:
    """The dispatches whose logs are read: those left a live state but not yet read to the end
    first, then the live ones, in roster order, at most `cap`."""
    entries = tuple(roster)
    ending = [entry for entry in entries if entry.dispatch_id in draining]
    live = [
        entry
        for entry in entries
        if entry.state in live_states and entry.dispatch_id not in draining
    ]
    return tuple((ending + live)[:cap])


def chunks(steps: Iterable[Step], budget: int = REPLY_BUDGET_BYTES) -> list[list[Step]]:
    """Consecutive steps in groups whose encoded size stays within `budget`; one step that alone
    exceeds it is a group of its own."""
    groups: list[list[Step]] = []
    used = budget
    for step in steps:
        size = len(json.dumps(step.to_wire(), ensure_ascii=False).encode("utf-8")) + 1
        if not groups or used + size > budget:
            groups.append([])
            used = 0
        groups[-1].append(step)
        used += size
    return groups
