"""Orchestration events of the console: what one poll observed, the compact view a later poll
compares with, the events between them and the journal cursor ``<journal>-<seq>``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ...kernel.json_fields import text
from ...kernel.protocol import ID_BYTES, MESSAGE_BYTES, _clip

type View = dict[str, object]
type Event = dict[str, object]
type Record = Mapping[str, object]


@dataclass(frozen=True)
class BatchFacts:
    ticket: str
    state: str
    # (dispatch_id, role, state of the batch entry), in the batch's order.
    dispatches: tuple[tuple[str, str, str], ...]
    decisions: tuple[Record, ...]


@dataclass(frozen=True)
class Observation:
    """What one poll read from the orchestration source."""

    store: str
    batches: dict[str, BatchFacts] = field(default_factory=dict)
    dispatch_states: dict[str, str] = field(default_factory=dict)
    qa_outcomes: dict[str, str] = field(default_factory=dict)
    qa_attempts: dict[str, Record] = field(default_factory=dict)


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


def parse_cursor(value: str) -> tuple[str, int] | None:
    """The journal id and the seq of a cursor ``<16 hex>-<seq>``; ``None`` when it is not one."""
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


def format_cursor(journal_id: str, seq: int) -> str:
    return f"{journal_id}-{seq}"
