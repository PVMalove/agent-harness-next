"""Worker steps for console clients: which log a dispatch has and the page a client receives.

A page is cut from one worker log by a byte offset that the client keeps; the server holds no
cursor, so a client continues after a server restart, and a shorter log answers ``reset``. Pure:
the caller reads the ledger records and the log.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from ...kernel.json_fields import text
from ...kernel.protocol import MESSAGE_BYTES, _clip

# Step text in one page: with the other fields the reply stays below `MESSAGE_LIMIT`.
STEP_BUDGET_BYTES = 48 * 1024
RECEIPT_PROTOCOL = "harness-worker-v1"
SOURCES = ("structured", "plain", "none")
STATES = ("connected", "waiting", "unavailable")
REASONS = (
    "no_log",
    "log_missing",
    "log_unreadable",
    "log_outside_storage",
    "log_unrecognised",
)
NO_LOG_MESSAGE = "Worker supplied no observable log; worker outcome is independent"
_DISPATCH_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}")


def valid_dispatch_id(value: str) -> bool:
    """A single file name: the ledger record of the dispatch is looked up by it."""
    return _DISPATCH_ID.fullmatch(value) is not None


@dataclass(frozen=True)
class WorkerFacts:
    """The dispatch record and its status record, as read from the ledger without its lock."""

    dispatch_id: str
    dispatch: Mapping[str, object]
    status: Mapping[str, object] | None


@dataclass(frozen=True)
class WorkerStep:
    kind: str
    text: str


@dataclass(frozen=True)
class StepsPage:
    """One page of worker steps; ``structure`` is ``unavailable`` for a plain log tail."""

    dispatch_id: str
    source: str
    structure: str
    state: str
    reason: str | None
    message: str
    offset: int
    reset: bool
    more: bool
    last_step_age_seconds: int | None
    steps: tuple[WorkerStep, ...]

    def to_wire(self) -> dict[str, object]:
        return {
            "dispatch_id": self.dispatch_id,
            "source": self.source,
            "structure": self.structure,
            "state": self.state,
            "reason": self.reason,
            "message": self.message,
            "offset": self.offset,
            "reset": self.reset,
            "more": self.more,
            "last_step_age_seconds": self.last_step_age_seconds,
            "steps": [{"kind": step.kind, "text": step.text} for step in self.steps],
        }


def select_source(facts: WorkerFacts) -> str:
    """A supervised worker's run log or a bound runtime receipt gives structured steps; an
    external adapter gives a plain log."""
    if facts.dispatch.get("execution"):
        return "structured"
    receipt = facts.status.get("adapter_receipt") if facts.status else None
    if (
        isinstance(receipt, Mapping)
        and receipt.get("protocol") == RECEIPT_PROTOCOL
        and receipt.get("dispatch_id") == facts.dispatch_id
        and isinstance(receipt.get("log_path"), str)
    ):
        return "structured"
    if facts.dispatch.get("resolved_transport") == "external":
        return "plain"
    return "none"


def in_process(facts: WorkerFacts) -> bool:
    """An in-process worker runs inside the coordinator session and writes no step log."""
    return facts.dispatch.get("resolved_transport") == "in-process"


def no_log_page(dispatch_id: str, offset: int) -> StepsPage:
    return StepsPage(
        dispatch_id=dispatch_id,
        source="none",
        structure="unavailable",
        state="unavailable",
        reason="no_log",
        message=NO_LOG_MESSAGE,
        offset=max(0, offset),
        reset=False,
        more=False,
        last_step_age_seconds=None,
        steps=(),
    )


def page_from_reading(dispatch_id: str, reading: Mapping[str, object]) -> StepsPage:
    """Only the page fields and each step's kind and text reach a client."""
    steps = reading.get("steps")
    reason = reading.get("reason")
    age = reading.get("last_step_age_seconds")
    offset = reading.get("offset")
    source = text(reading.get("source"))
    state = text(reading.get("state"))
    return StepsPage(
        dispatch_id=dispatch_id,
        source=source if source in SOURCES else "none",
        structure="available" if source == "structured" else "unavailable",
        state=state if state in STATES else "unavailable",
        reason=reason if isinstance(reason, str) and reason in REASONS else None,
        message=_clip(text(reading.get("message")), MESSAGE_BYTES),
        offset=offset if isinstance(offset, int) and offset >= 0 else 0,
        reset=reading.get("reset") is True,
        more=reading.get("more") is True,
        last_step_age_seconds=age if isinstance(age, int) else None,
        steps=tuple(
            WorkerStep(kind=text(step.get("kind")), text=text(step.get("text")))
            for step in (steps if isinstance(steps, list) else [])
            if isinstance(step, Mapping)
        ),
    )


def worth_sending(previous: StepsPage | None, page: StepsPage) -> bool:
    """A stream sends new steps, a reset and a changed state; an unchanged wait stays quiet."""
    return (
        previous is None
        or bool(page.steps)
        or page.reset
        or (page.state, page.reason) != (previous.state, previous.reason)
    )
