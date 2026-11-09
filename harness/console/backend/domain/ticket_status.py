"""The status-change rules of the task board: the one place that decides whether a ticket may move
from its board column to another and which `status::*` labels the move replaces. The CLI command
and the board snapshot both use it, so the page never enforces a rule of its own.

Pure: the column, the blockers and the batch come from the caller; nothing here does I/O."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .task_board import COLUMNS

# The single `status::*` label of each column a move can write. Backlog keeps `status::blocked`,
# so a ticket always carries exactly one status label after a move.
STATUS_LABEL = {
    "backlog": "status::blocked",
    "ready": "status::ready",
    "progress": "status::in-progress",
}
# Every refusal reason; `same` is a move onto the ticket's own column.
REASONS = (
    "same",
    "review_target",
    "done_target",
    "closed",
    "in_review",
    "open_blockers",
    "active_batch",
    "via_ready",
)


@dataclass(frozen=True)
class MoveFacts:
    """What a move depends on: the ticket's board column (None for a ticket the board leaves
    out), its open blockers, the blockers of unknown state and its active batch."""

    column: str | None
    open_blockers: tuple[str, ...] = ()
    unknown_blockers: tuple[str, ...] = ()
    batch: str | None = None


@dataclass(frozen=True)
class Move:
    """The decision about one target column: allowed, or refused with a reason and the blockers
    or the batch that explain it."""

    to: str
    allowed: bool
    reason: str | None
    blockers: tuple[str, ...] = ()
    batch: str | None = None


def decide(facts: MoveFacts, to: str, *, strict: bool) -> Move:
    """Whether the ticket may move to column `to`. `strict` counts a blocker of unknown state as
    open (the write fails closed); without it only known open blockers refuse the move."""
    if to not in COLUMNS:
        raise ValueError(f"unknown column: {to}")
    source = facts.column or "done"
    if source == to:
        return Move(to, False, "same")
    if to == "review":
        return Move(to, False, "review_target")
    if to == "done":
        return Move(to, False, "done_target")
    if source == "done":
        return Move(to, False, "closed")
    if source == "review":
        return Move(to, False, "in_review")
    if source == "backlog" and to == "ready":
        blockers = facts.open_blockers + (facts.unknown_blockers if strict else ())
        if blockers:
            return Move(to, False, "open_blockers", blockers=blockers)
        return Move(to, True, None)
    if source == "ready" and to in {"backlog", "progress"}:
        return Move(to, True, None)
    if source == "progress" and to == "ready":
        if facts.batch:
            return Move(to, False, "active_batch", batch=facts.batch)
        return Move(to, True, None)
    return Move(to, False, "via_ready")


def moves(facts: MoveFacts, *, strict: bool) -> list[Move]:
    """The decision for every board column, in board order."""
    return [decide(facts, column, strict=strict) for column in COLUMNS]


def relabel(labels: Iterable[str], to: str) -> tuple[tuple[str, ...], str]:
    """The `status::*` labels a move to `to` removes (every one but the target's) and the label it
    adds; a column without a label of its own is a `ValueError`."""
    if to not in STATUS_LABEL:
        raise ValueError(f"no status label for column: {to}")
    target = STATUS_LABEL[to]
    remove = tuple(
        dict.fromkeys(
            label
            for label in labels
            if label.startswith("status::") and label != target
        )
    )
    return remove, target
