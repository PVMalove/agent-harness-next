"""The status change of one ticket: read fresh tracker and ledger facts (never the board cache),
decide the move with the domain rules, then write the `status::*` label only when it is allowed.
The CLI command runs it, so the rules hold for every caller, not only the web page."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ...kernel.reports import LedgerView
from ..domain.task_board import (
    SpecTickets,
    TrackerTicket,
    batch_stages,
    column,
    ticket_blockers,
)
from ..domain.ticket_status import MoveFacts, decide, relabel
from .ports import SpecNotFound, TrackerUnavailable

# The exit code of each result: a refusal never wrote anything.
EXIT_CODES = {"changed": 0, "refused": 3, "write_error": 1}

_MESSAGES = {
    "same": "the ticket is already in this column",
    "review_target": "Review / QA is computed from the dispatch and the PR; a card is not moved there",
    "done_target": "Done is filled by closing the ticket after a confirmed merge",
    "closed": "a closed ticket is not moved",
    "in_review": "the ticket has an active batch in review or an open PR",
    "open_blockers": "open blockers",
    "active_batch": "active batch",
    "via_ready": "the move goes through Ready",
    "not_found": "the ticket is not a sub-ticket of the spec",
    "ledger_unavailable": "the orchestration ledger cannot be read",
}


class _Reader(Protocol):
    def board(self, repo: Path, spec_ref: str) -> SpecTickets: ...


class _Writer(Protocol):
    def write(
        self, repo: Path, ticket: TrackerTicket, remove: tuple[str, ...], add: str
    ) -> None: ...

    def blocker_closed(self, repo: Path, ref: str) -> bool | None: ...


@dataclass(frozen=True)
class Outcome:
    """The result line of a status change."""

    ticket: str
    source: str | None
    to: str
    result: str
    reason: str | None = None
    blockers: tuple[str, ...] = ()
    batch: str | None = None
    message: str = ""

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.result]

    def to_json(self) -> dict[str, object]:
        return {
            "ticket": self.ticket,
            "from": self.source,
            "to": self.to,
            "result": self.result,
            "reason": self.reason,
            "blockers": list(self.blockers),
            "batch": self.batch,
            "message": self.message,
        }


def _find(board: SpecTickets, ref: str) -> TrackerTicket | None:
    wanted = ref.strip()
    for ticket in board.tickets:
        if ticket.ref == wanted:
            return ticket
    number = wanted.removeprefix("#")
    if number.isdigit():
        return next(
            (
                ticket
                for ticket in board.tickets
                if ticket.ref.startswith("#") and ticket.n == int(number)
            ),
            None,
        )
    return None


def _message(reason: str, blockers: tuple[str, ...], batch: str | None) -> str:
    text = _MESSAGES.get(reason, reason)
    if blockers:
        return f"{text}: {', '.join(blockers)}"
    if batch:
        return f"{text} {batch}"
    return text


def change_status(
    repo: Path,
    *,
    spec: str,
    ticket: str,
    to: str,
    reader: _Reader,
    ledger: Callable[[Path], LedgerView],
    writer: _Writer,
) -> Outcome:
    """Move `ticket` of `spec` to column `to`, or refuse with the reason."""

    def refused(
        source: str | None,
        reason: str,
        blockers: tuple[str, ...] = (),
        batch: str | None = None,
    ) -> Outcome:
        message = _message(reason, blockers, batch)
        return Outcome(ticket, source, to, "refused", reason, blockers, batch, message)

    try:
        board = reader.board(repo, spec)
    except SpecNotFound:
        return refused(None, "not_found")
    except TrackerUnavailable as failure:
        return Outcome(
            ticket, None, to, "write_error", "tracker_unavailable", message=failure.message
        )
    found = _find(board, ticket)
    if found is None:
        return refused(None, "not_found")
    ticket = found.ref
    try:
        view = ledger(repo)
        stage = batch_stages(view).get(found.ref)
        ledger_ok = True
    except Exception:  # an unreadable ledger only refuses the moves that depend on it
        stage, ledger_ok = None, False
    source = column(found, stage)
    blockers = ticket_blockers(found, board.blocker_states)
    open_refs = tuple(str(item["id"]) for item in blockers if item["state"] == "open")
    unknown = [str(item["id"]) for item in blockers if item["state"] == "unknown"]
    if source == "backlog" and to == "ready" and not open_refs:
        # The board could not tell these states; read each once, and fail closed on silence.
        unknown = [ref for ref in unknown if writer.blocker_closed(repo, ref) is not True]
    move = decide(
        MoveFacts(source, open_refs, tuple(unknown), stage.batch_id if stage else None),
        to,
        strict=True,
    )
    if not move.allowed:
        return refused(source, str(move.reason), move.blockers, move.batch)
    if source == "progress" and not ledger_ok:
        return refused(source, "ledger_unavailable")
    remove, add = relabel(found.labels, to)
    try:
        writer.write(repo, found, remove, add)
    except Exception as exc:  # noqa: BLE001 - every write failure is reported, never raised
        return Outcome(
            ticket, source, to, "write_error", "write_failed", message=str(exc) or type(exc).__name__
        )
    changed = f"{', '.join(remove) or '-'} -> {add}"
    return Outcome(ticket, source, to, "changed", message=changed)
