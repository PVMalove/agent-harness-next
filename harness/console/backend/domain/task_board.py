"""The task-board rules: how a ticket body is read, which column a ticket sits in, which command
starts it, the agent prompt, the current batch stage of each ticket and the bounded board payloads.
Pure: the tracker facts and the ledger view come from the caller; nothing here does I/O."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from ....orchestration.core.constants import TERMINAL_BATCH_STATES
from ...kernel.protocol import MESSAGE_BYTES, _clip

BOARD_TTL_SECONDS = 60.0
# Spec boards kept for the stale fallback; the least recently served goes first.
KEPT_BOARDS = 8
REVIEW_ROLES = frozenset({"code-review", "qa"})
COLUMNS = ("backlog", "ready", "progress", "review", "done")
# Caps in wire bytes (a JSON string's encoded size), counts in items.
BODY_READ_BYTES = 65536
TITLE_BYTES = 300
URL_BYTES = 2048
WHAT_BYTES = 8192
CRITERIA_MAX = 30
CRITERION_BYTES = 600
FILES_MAX = 40
PATH_BYTES = 300
WHY_BYTES = 300
LABELS_MAX = 30
LABEL_BYTES = 100
BLOCKERS_MAX = 20
BLOCKER_BYTES = 300
BRANCH_BYTES = 200
MAX_TICKETS = 200
MAX_SPECS = 200
# The JSON size of one board payload; the cards past it are left out.
BOARD_BYTES = 8 * 1024 * 1024
REASON_BYTES = MESSAGE_BYTES

_TERMINAL = frozenset(str(state) for state in TERMINAL_BATCH_STATES)


@dataclass(frozen=True)
class BlockerFact:
    """A blocker the tracker records natively; `closed` is None when its state is unknown."""

    ref: str
    n: int | None
    title: str
    closed: bool | None


@dataclass(frozen=True)
class PullRef:
    """An open PR ("#958") or MR ("!12") of a ticket."""

    ref: str
    url: str | None


@dataclass(frozen=True)
class TrackerTicket:
    """One sub-ticket of a spec as the tracker returns it, the body still unparsed."""

    ref: str
    n: int | None
    title: str
    url: str | None
    closed: bool
    labels: tuple[str, ...]
    body: str
    native_blockers: tuple[BlockerFact, ...] = ()
    pr: PullRef | None = None


@dataclass(frozen=True)
class TrackerSpec:
    """An open spec (epic) with the sub-ticket counts the tracker knows, if any."""

    ref: str
    n: int | None
    title: str
    url: str | None
    body: str
    tickets_total: int | None
    tickets_open: int | None


@dataclass(frozen=True)
class SpecList:
    """The open specs the tracker returned; `truncated` when its listing stopped at a limit."""

    specs: tuple[TrackerSpec, ...]
    truncated: bool = False


@dataclass(frozen=True)
class SpecTickets:
    """A spec with its sub-tickets and the known closed state of tickets referenced as blockers;
    `truncated` when the tracker listing stopped at a limit."""

    spec: TrackerSpec
    tickets: tuple[TrackerTicket, ...]
    blocker_states: Mapping[str, bool]
    truncated: bool = False


@dataclass(frozen=True)
class TicketBody:
    """What the board reads from a ticket body; every field already capped."""

    what: str
    criteria: tuple[str, ...]
    files: tuple[tuple[str, str], ...]
    blocked_by: tuple[tuple[str, int | None, str], ...]
    branch: str | None
    story_points: int | None
    truncated: bool = False


@dataclass(frozen=True)
class BatchStage:
    """The open batch of a ticket and the role and state of its current dispatch."""

    batch_id: str
    batch_state: str
    role: str | None
    dispatch_state: str | None


class _Batch(Protocol):
    @property
    def batch_id(self) -> str: ...
    @property
    def ticket(self) -> str: ...
    @property
    def state(self) -> str: ...
    @property
    def created_at(self) -> str: ...


class _Stage(Protocol):
    @property
    def batch_id(self) -> str: ...
    @property
    def role(self) -> str: ...
    @property
    def state(self) -> str: ...
    @property
    def at(self) -> str: ...


class LedgerFacts(Protocol):
    """What the board reads of the orchestration ledger view."""

    @property
    def batches(self) -> Sequence[_Batch]: ...
    @property
    def stages(self) -> Sequence[_Stage]: ...
    @property
    def unavailable(self) -> str | None: ...


class _Caps:
    """Clips texts to wire-byte caps and remembers whether any cap fired."""

    def __init__(self) -> None:
        self.fired = False

    def text(self, value: str, limit: int) -> str:
        clipped = _clip(value, limit)
        if clipped != value:
            self.fired = True
        return clipped

    def items(self, values: Sequence[object], limit: int) -> int:
        if len(values) > limit:
            self.fired = True
            return limit
        return len(values)


# Every pattern runs on untrusted ticket text: no two adjacent quantifiers may match the same
# characters, or a long whitespace run costs quadratic or cubic time while holding the GIL.
_HEADING = re.compile(r"^##\s+(.*)$")
_FIELD = re.compile(r"^\*\*([^*]+?):\*\*\s*(.*)$")
_ITEM = re.compile(r"^\s{0,3}(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d{1,4}[.)]\s+)(.*)$")
_CHECKBOX = re.compile(r"^[-*+]\s+\[[ xX]\]\s+(.*)$")
_MENTION = re.compile(r"(?<![\w/])([#!]?)(\d{1,9})\b")
_REASON = re.compile(r"(?<!\s)\s+[—–-]\s+|:\s*|(?<!\s)\s*[—–]\s*")
_FILE_SPLIT = re.compile(r"(?<!\s)\s+[—–-]\s+|:\s+")
_BLOCKED_PREFIX = re.compile(r"^(?:[-*+]\s+)?(?:\*\*)?blocked by:?(?:\*\*)?:?\s*", re.I)
_BACKTICK = re.compile(r"`([^`]+)`")
_INT = re.compile(r"\d{1,6}")


def _section(name: str) -> str | None:
    lowered = name.casefold()
    if lowered.startswith("what to build"):
        return "what"
    if lowered.startswith("acceptance criteria"):
        return "criteria"
    if "discovery context" in lowered:
        return "files"
    if lowered.startswith("blocked by"):
        return "blocked"
    if lowered.startswith("integration branch"):
        return "branch"
    if lowered.startswith("story points"):
        return "sp"
    return None


def _items(lines: Iterable[str]) -> list[str]:
    """List items with indented continuation lines joined by a space."""
    found: list[str] = []
    for line in lines:
        match = _ITEM.match(line)
        if match:
            found.append(match.group(1).strip())
        elif found and line[:1].isspace() and line.strip():
            found[-1] = f"{found[-1]} {line.strip()}"
    return [item for item in found if item]


def _file(item: str) -> tuple[str, str]:
    if item.startswith("`") and "`" in item[1:]:
        end = item.index("`", 1)
        path, rest = item[1:end], item[end + 1 :]
    else:
        parts = _FILE_SPLIT.split(item, maxsplit=1)
        path, rest = parts[0], (parts[1] if len(parts) > 1 else "")
    why = re.sub(r"^\s*[—–:-]\s*", "", rest).strip()
    return path.strip(), why


def _blockers(line: str) -> list[tuple[str, int | None, str]]:
    text = _BLOCKED_PREFIX.sub("", line.strip()).strip()
    if not text or text.casefold().startswith("none"):
        return []
    head, reason = text, ""
    split = _REASON.search(text)
    if split is not None and _MENTION.search(text[: split.start()]):
        head, reason = text[: split.start()], text[split.end() :].strip()
    found: list[tuple[str, int | None, str]] = []
    for mark, digits in _MENTION.findall(head):
        number = int(digits)
        found.append((f"{mark}{number}" if mark else digits, number, reason))
    return found


def _branch(lines: Sequence[str]) -> str | None:
    for line in lines:
        match = _BACKTICK.search(line)
        if match:
            return match.group(1).strip() or None
    for line in lines:
        if line.strip():
            return line.strip()
    return None


def _story_points(lines: Iterable[str]) -> int | None:
    for line in lines:
        match = _INT.search(line)
        if match:
            return int(match.group(0))
    return None


def parse_body(body: str) -> TicketBody:
    """Read the board fields of a ticket body: the `## ` sections of the issue template and the
    `**Field:**` lines of the local template. Never raises; every field is capped."""
    caps = _Caps()
    text = caps.text(body, BODY_READ_BYTES).replace("\r\n", "\n").replace("\r", "\n")
    sections: dict[str, list[str]] = {}
    inline: dict[str, list[str]] = {}
    loose: list[str] = []
    current: str | None = None
    for line in text.split("\n"):
        heading = _HEADING.match(line)
        if heading:
            current = _section(heading.group(1).rstrip().rstrip("#").rstrip())
            if current is not None:
                sections.setdefault(current, [])
            continue
        field = _FIELD.match(line.strip())
        if field:
            # A `**Field:**` line of the local template ends the `## ` section before it.
            current = None
            if (key := _section(field.group(1))) is not None:
                inline.setdefault(key, []).append(field.group(2))
            continue
        if current is not None:
            sections[current].append(line)
        else:
            loose.append(line)

    def lines(key: str) -> list[str]:
        return sections.get(key) or inline.get(key) or []

    what = caps.text("\n".join(lines("what")).strip(), WHAT_BYTES)
    if "criteria" in sections:
        raw_criteria = _items(sections["criteria"])
    else:
        raw_criteria = [
            match.group(1).strip()
            for line in loose
            if (match := _CHECKBOX.match(line)) and match.group(1).strip()
        ]
    criteria = tuple(
        caps.text(item, CRITERION_BYTES)
        for item in raw_criteria[: caps.items(raw_criteria, CRITERIA_MAX)]
    )
    raw_files = [_file(item) for item in _items(lines("files"))]
    files = tuple(
        (caps.text(path, PATH_BYTES), caps.text(why, WHY_BYTES))
        for path, why in raw_files[: caps.items(raw_files, FILES_MAX)]
        if path
    )
    raw_blocked = [found for line in lines("blocked") for found in _blockers(line)]
    blocked_by = tuple(
        (caps.text(ref, LABEL_BYTES), number, caps.text(reason, BLOCKER_BYTES))
        for ref, number, reason in raw_blocked[: caps.items(raw_blocked, BLOCKERS_MAX)]
    )
    branch = _branch(lines("branch"))
    return TicketBody(
        what=what,
        criteria=criteria,
        files=files,
        blocked_by=blocked_by,
        branch=caps.text(branch, BRANCH_BYTES) if branch else None,
        story_points=_story_points(lines("sp")),
        truncated=caps.fired,
    )


def _status(labels: Iterable[str]) -> str:
    return next((label for label in labels if label.startswith("status::")), "")


def column(ticket: TrackerTicket, stage: BatchStage | None) -> str | None:
    """The board column of a ticket; None for a closed `resolution::wontfix` ticket, which the
    board leaves out."""
    if ticket.closed:
        return None if "resolution::wontfix" in ticket.labels else "done"
    status = _status(ticket.labels)
    if status == "status::in-progress":
        in_review = (stage is not None and stage.role in REVIEW_ROLES) or ticket.pr
        return "review" if in_review else "progress"
    return "ready" if status == "status::ready" else "backlog"


def launch_command(labels: Iterable[str]) -> str:
    """The command that starts a ticket: `hitl` goes to `/to-guide`, `afk` with
    `pipeline::fast` to `/fast-implement`, everything else (also an unlabeled ticket) to
    `/implement`."""
    names = set(labels)
    if "hitl" in names:
        return "/to-guide"
    if "afk" in names and "pipeline::fast" in names:
        return "/fast-implement"
    return "/implement"


def _str(value: object) -> str:
    return value if isinstance(value, str) else ""


def _dicts(value: object) -> list[Mapping[str, object]]:
    return (
        [item for item in value if isinstance(item, Mapping)]
        if isinstance(value, list)
        else []
    )


def agent_prompt(card: Mapping[str, object], spec: Mapping[str, object]) -> str:
    """The ready agent prompt of a board card: the launch command first, then the ticket, epic,
    branch, What to build, acceptance criteria, blockers and Discovery Context."""
    ref = _str(card.get("id"))
    blockers = [
        "- "
        + _str(item.get("id"))
        + (f" — {why}" if (why := _str(item.get("why"))) else "")
        + (" (closed)" if item.get("state") == "closed" else "")
        for item in _dicts(card.get("blockers"))
    ]
    files = [
        "- "
        + _str(item.get("path"))
        + (f" — {why}" if (why := _str(item.get("why"))) else "")
        for item in _dicts(card.get("files"))
    ]
    criteria = card.get("criteria")
    branch = _str(card.get("branch")) or _str(spec.get("branch")) or "not recorded"
    return "\n".join(
        [
            f"{_str(card.get('command'))} {ref}",
            "",
            f"TICKET: {ref} — {_str(card.get('title'))}",
            f"EPIC: {_str(spec.get('id'))} — {_str(spec.get('title'))}",
            f"BRANCH: {branch}",
            "",
            "WHAT TO BUILD:",
            _str(card.get("what")),
            "",
            "ACCEPTANCE:",
            *(
                f"{index}. {_str(item)}"
                for index, item in enumerate(
                    criteria if isinstance(criteria, list) else [], 1
                )
            ),
            "",
            "BLOCKERS:",
            *(blockers or ["- None"]),
            "",
            "DISCOVERY:",
            *(files or ["- None"]),
        ]
    )


def batch_stages(view: LedgerFacts) -> dict[str, BatchStage]:
    """The newest open batch of every ticket with its current (latest) dispatch; an unavailable
    ledger gives none."""
    if view.unavailable:
        return {}
    newest: dict[str, _Batch] = {}
    for batch in view.batches:
        if str(batch.state) in _TERMINAL or not batch.ticket:
            continue
        known = newest.get(batch.ticket)
        if known is None or batch.created_at > known.created_at:
            newest[batch.ticket] = batch
    latest: dict[str, _Stage] = {}
    for stage in view.stages:
        known_stage = latest.get(stage.batch_id)
        if known_stage is None or stage.at > known_stage.at:
            latest[stage.batch_id] = stage
    stages = {}
    for ticket, batch in newest.items():
        current = latest.get(batch.batch_id)
        stages[ticket] = BatchStage(
            batch.batch_id,
            str(batch.state),
            current.role if current is not None else None,
            str(current.state) if current is not None else None,
        )
    return stages


def _spec_branch(spec: TrackerSpec) -> str | None:
    return parse_body(spec.body).branch


def build_specs_payload(
    tracker_type: str, specs: SpecList | Sequence[TrackerSpec]
) -> dict[str, object]:
    """The `task_board.specs` payload: the open specs, at most `MAX_SPECS`."""
    listing = specs if isinstance(specs, SpecList) else SpecList(tuple(specs))
    caps = _Caps()
    caps.fired = listing.truncated
    shown = listing.specs[: caps.items(listing.specs, MAX_SPECS)]
    return {
        "tracker": tracker_type,
        "stale": None,
        "age_seconds": None,
        "specs": [
            {
                "id": caps.text(spec.ref, PATH_BYTES),
                "n": spec.n,
                "title": caps.text(spec.title, TITLE_BYTES),
                "url": caps.text(spec.url, URL_BYTES) if spec.url else None,
                "branch": _spec_branch(spec),
                "tickets_total": spec.tickets_total,
                "tickets_open": spec.tickets_open,
            }
            for spec in shown
        ],
        "truncated": caps.fired,
    }


def _blocker_cards(
    ticket: TrackerTicket,
    body: TicketBody,
    states: Mapping[str, bool],
    caps: _Caps,
) -> list[dict[str, object]]:
    merged: dict[object, dict[str, object]] = {}
    for ref, number, reason in body.blocked_by:
        key = number if number is not None else ref
        merged.setdefault(key, {"id": ref, "n": number, "why": reason, "closed": None})
    for fact in ticket.native_blockers:
        key = fact.n if fact.n is not None else fact.ref
        entry = merged.setdefault(
            key, {"id": fact.ref, "n": fact.n, "why": "", "closed": None}
        )
        entry["id"] = fact.ref
        if not entry["why"]:
            entry["why"] = caps.text(fact.title, BLOCKER_BYTES)
        if fact.closed is not None:
            entry["closed"] = fact.closed
    cards = []
    for entry in list(merged.values())[: caps.items(list(merged), BLOCKERS_MAX)]:
        closed = entry.pop("closed")
        if closed is None:
            ref = str(entry["id"])
            closed = states.get(ref)
            if closed is None and entry["n"] is not None:
                closed = states.get(f"#{entry['n']}")
        entry["id"] = caps.text(str(entry["id"]), PATH_BYTES)
        entry["state"] = "unknown" if closed is None else "closed" if closed else "open"
        cards.append(entry)
    return cards


def _json_bytes(value: object) -> int:
    """An upper bound of the bytes `value` takes as JSON on the wire: every non-ASCII character
    counted as its `\\uXXXX` escape."""
    return len(json.dumps(value))


def _sort_key(ticket: TrackerTicket) -> tuple[int, int, str]:
    return (ticket.n is None, ticket.n or 0, ticket.ref)


def _priority_rank(card: Mapping[str, object]) -> int:
    """`priority::p0` first, a card without a priority last."""
    label = card.get("priority")
    if isinstance(label, str) and label.removeprefix("priority::p").isdigit():
        return int(label.removeprefix("priority::p"))
    return len(COLUMNS) + 99


def order_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    """The cards in board order: by column, then priority, then ticket number, so any client lists
    one column the same way."""
    return sorted(
        cards,
        key=lambda card: (
            COLUMNS.index(str(card["column"])),
            _priority_rank(card),
            card["n"] is None,
            card["n"] or 0,
            str(card["id"]),
        ),
    )


def build_board_payload(
    tracker_type: str,
    board: SpecTickets,
    stages: Mapping[str, BatchStage],
    ledger_ok: bool,
) -> dict[str, object]:
    """The `task_board.snapshot` payload of one spec: its cards with columns, blockers, batch
    stage and prompt, and the KPIs. Closed `resolution::wontfix` tickets are left out."""
    caps = _Caps()
    caps.fired = board.truncated
    shown = sorted(
        (
            ticket
            for ticket in board.tickets
            if not (ticket.closed and "resolution::wontfix" in ticket.labels)
        ),
        key=_sort_key,
    )
    shown = shown[: caps.items(shown, MAX_TICKETS)]
    bodies = [parse_body(ticket.body) for ticket in shown]
    spec = board.spec
    branch = _spec_branch(spec)
    if branch is None:
        common = Counter(body.branch for body in bodies if body.branch).most_common(1)
        branch = common[0][0] if common else None
    spec_card: dict[str, object] = {
        "id": caps.text(spec.ref, PATH_BYTES),
        "n": spec.n,
        "title": caps.text(spec.title, TITLE_BYTES),
        "url": caps.text(spec.url, URL_BYTES) if spec.url else None,
        "branch": branch,
    }
    cards: list[dict[str, object]] = []
    # The spec card, the KPIs and the other fields stay far below the reserve.
    used = _json_bytes(spec_card) + 4096
    for ticket, body in zip(shown, bodies, strict=True):
        own = _Caps()
        stage = stages.get(ticket.ref)
        labels = [
            own.text(label, LABEL_BYTES)
            for label in ticket.labels[: own.items(ticket.labels, LABELS_MAX)]
        ]
        blockers = _blocker_cards(ticket, body, board.blocker_states, own)
        card: dict[str, object] = {
            "id": own.text(ticket.ref, PATH_BYTES),
            "n": ticket.n,
            "title": own.text(ticket.title, TITLE_BYTES),
            "url": own.text(ticket.url, URL_BYTES) if ticket.url else None,
            "closed": ticket.closed,
            "column": column(ticket, stage),
            "labels": labels,
            "priority": next(
                (label for label in labels if label.startswith("priority::")), None
            ),
            "sp": body.story_points,
            "command": launch_command(ticket.labels),
            "branch": body.branch,
            "what": body.what,
            "criteria": list(body.criteria),
            "files": [{"path": path, "why": why} for path, why in body.files],
            "blockers": blockers,
            "open_blockers": sum(item["state"] == "open" for item in blockers),
            "pr": (
                {
                    "ref": own.text(ticket.pr.ref, LABEL_BYTES),
                    "url": own.text(ticket.pr.url, URL_BYTES)
                    if ticket.pr.url
                    else None,
                }
                if ticket.pr is not None
                else None
            ),
            "batch": stage.batch_id if stage else None,
            "batch_state": stage.batch_state if stage else None,
            "dispatch": stage.role if stage else None,
            "dispatch_state": stage.dispatch_state if stage else None,
        }
        card["prompt"] = agent_prompt(card, spec_card)
        card["truncated"] = own.fired or body.truncated
        used += _json_bytes(card)
        if used > BOARD_BYTES:
            caps.fired = True
            break
        caps.fired = caps.fired or bool(card["truncated"])
        cards.append(card)
    cards = order_cards(cards)
    return {
        "tracker": tracker_type,
        "stale": None,
        "age_seconds": None,
        "ledger": "ok" if ledger_ok else "unavailable",
        "spec": spec_card,
        "columns": [
            {
                "id": column_id,
                "count": sum(card["column"] == column_id for card in cards),
            }
            for column_id in COLUMNS
        ],
        "kpis": {
            "open": sum(not card["closed"] for card in cards),
            "total": len(cards),
            "with_open_blockers": sum(bool(card["open_blockers"]) for card in cards),
            "active_batch": sum(card["batch"] is not None for card in cards),
        },
        "tickets": cards,
        "truncated": caps.fired,
    }
