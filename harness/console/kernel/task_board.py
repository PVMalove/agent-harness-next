"""The task board the console server returns for the Web console and the TUI.

The server builds the payload; this module only validates it and gives the TUI plain dataclasses,
like the other kernel snapshot modules. Standard library only: the board screen and its tests can
run without Textual or the server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class BoardSpec:
    """One open spec (epic) and its ticket counters."""

    id: str
    n: int
    title: str
    url: str | None
    branch: str | None
    tickets_total: int = 0
    tickets_open: int = 0


@dataclass(frozen=True)
class BoardSpecs:
    """The open specs of the project."""

    tracker: str
    specs: tuple[BoardSpec, ...]
    stale: str | None
    age_seconds: int | None
    truncated: bool


@dataclass(frozen=True)
class BoardBlocker:
    """A blocker of a board card; `state` is `open`, `closed` or `unknown`."""

    id: str
    n: int | None
    why: str
    state: str


@dataclass(frozen=True)
class BoardPull:
    """The open PR/MR of a card."""

    ref: str
    url: str | None


@dataclass(frozen=True)
class BoardCard:
    """One ticket of a spec board, with the fields the card and its modal show."""

    id: str
    n: int | None
    title: str
    url: str | None
    closed: bool
    column: str
    labels: tuple[str, ...]
    priority: str | None
    sp: int | None
    command: str
    branch: str | None
    what: str
    criteria: tuple[str, ...]
    files: tuple[tuple[str, str], ...]
    blockers: tuple[BoardBlocker, ...]
    open_blockers: int
    pr: BoardPull | None
    batch: str | None
    batch_state: str | None
    dispatch: str | None
    dispatch_state: str | None
    prompt: str
    truncated: bool


@dataclass(frozen=True)
class BoardSnapshot:
    """One spec board: its spec, columns, KPIs and cards."""

    tracker: str
    ledger: str
    spec: BoardSpec
    columns: tuple[str, ...]
    kpis: Mapping[str, int]
    tickets: tuple[BoardCard, ...]
    truncated: bool


def _dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is not an object")
    return value


def _list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{what} is not a list")
    return value


def _str(value: object, what: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{what} is not a string")
    return value


def _int(value: object, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{what} is not an integer")
    return value


def _optional_int(value: object, what: str) -> int | None:
    if value is None:
        return None
    return _int(value, what)


def _optional_str(value: object, what: str) -> str | None:
    if value is None:
        return None
    return _str(value, what)


def _spec(value: object, *, totals: bool) -> BoardSpec:
    found = _dict(value, "spec")
    return BoardSpec(
        id=_str(found.get("id"), "spec.id"),
        n=_int(found.get("n"), "spec.n"),
        title=_str(found.get("title"), "spec.title"),
        url=_optional_str(found.get("url"), "spec.url"),
        branch=_optional_str(found.get("branch"), "spec.branch"),
        tickets_total=_int(found.get("tickets_total"), "spec.tickets_total")
        if totals
        else 0,
        tickets_open=_int(found.get("tickets_open"), "spec.tickets_open")
        if totals
        else 0,
    )


def specs_from_payload(value: object) -> BoardSpecs:
    """The `task_board.specs` payload; `ValueError` when it is outside the schema."""
    found = _dict(value, "specs")
    specs = tuple(
        _spec(item, totals=True) for item in _list(found.get("specs"), "specs.specs")
    )
    return BoardSpecs(
        tracker=_str(found.get("tracker"), "specs.tracker"),
        specs=specs,
        stale=_optional_str(found.get("stale"), "specs.stale"),
        age_seconds=_optional_int(found.get("age_seconds"), "specs.age_seconds"),
        truncated=bool(found.get("truncated", False)),
    )


def _blocker(value: object) -> BoardBlocker:
    found = _dict(value, "blocker")
    state = _str(found.get("state"), "blocker.state")
    if state not in {"open", "closed", "unknown"}:
        raise ValueError("blocker.state is unknown")
    return BoardBlocker(
        id=_str(found.get("id"), "blocker.id"),
        n=_optional_int(found.get("n"), "blocker.n"),
        why=_str(found.get("why"), "blocker.why"),
        state=state,
    )


def _pull(value: object) -> BoardPull | None:
    if value is None:
        return None
    found = _dict(value, "pr")
    return BoardPull(
        ref=_str(found.get("ref"), "pr.ref"),
        url=_optional_str(found.get("url"), "pr.url"),
    )


def _card(value: object) -> BoardCard:
    found = _dict(value, "ticket")
    labels = tuple(
        _str(item, "ticket.labels[]")
        for item in _list(found.get("labels"), "ticket.labels")
    )
    criteria = tuple(
        _str(item, "ticket.criteria[]")
        for item in _list(found.get("criteria"), "ticket.criteria")
    )
    files = []
    for item in _list(found.get("files"), "ticket.files"):
        file = _dict(item, "ticket.files[]")
        files.append(
            (_str(file.get("path"), "file.path"), _str(file.get("why"), "file.why"))
        )
    blockers = tuple(
        _blocker(item) for item in _list(found.get("blockers"), "ticket.blockers")
    )
    column = _str(found.get("column"), "ticket.column")
    if column not in {"backlog", "ready", "progress", "review", "done"}:
        raise ValueError("ticket.column is unknown")
    return BoardCard(
        id=_str(found.get("id"), "ticket.id"),
        n=_optional_int(found.get("n"), "ticket.n"),
        title=_str(found.get("title"), "ticket.title"),
        url=_optional_str(found.get("url"), "ticket.url"),
        closed=bool(found.get("closed", False)),
        column=column,
        labels=labels,
        priority=_optional_str(found.get("priority"), "ticket.priority"),
        sp=_optional_int(found.get("sp"), "ticket.sp"),
        command=_str(found.get("command"), "ticket.command"),
        branch=_optional_str(found.get("branch"), "ticket.branch"),
        what=_str(found.get("what"), "ticket.what"),
        criteria=criteria,
        files=tuple(files),
        blockers=blockers,
        open_blockers=_int(found.get("open_blockers"), "ticket.open_blockers"),
        pr=_pull(found.get("pr")),
        batch=_optional_str(found.get("batch"), "ticket.batch"),
        batch_state=_optional_str(found.get("batch_state"), "ticket.batch_state"),
        dispatch=_optional_str(found.get("dispatch"), "ticket.dispatch"),
        dispatch_state=_optional_str(
            found.get("dispatch_state"), "ticket.dispatch_state"
        ),
        prompt=_str(found.get("prompt"), "ticket.prompt"),
        truncated=bool(found.get("truncated", False)),
    )


def board_from_payload(value: object) -> BoardSnapshot:
    """The `task_board.snapshot` payload; `ValueError` when it is outside the schema."""
    found = _dict(value, "board")
    columns = tuple(
        _str(_dict(item, "column").get("id"), "column.id")
        for item in _list(found.get("columns"), "board.columns")
    )
    kpis_value = _dict(found.get("kpis"), "board.kpis")
    kpis = {
        key: _int(kpis_value.get(key), f"kpis.{key}")
        for key in ("open", "total", "with_open_blockers", "active_batch")
    }
    return BoardSnapshot(
        tracker=_str(found.get("tracker"), "board.tracker"),
        ledger=_str(found.get("ledger"), "board.ledger"),
        spec=_spec(found.get("spec"), totals=False),
        columns=columns,
        kpis=kpis,
        tickets=tuple(
            _card(item) for item in _list(found.get("tickets"), "board.tickets")
        ),
        truncated=bool(found.get("truncated", False)),
    )
