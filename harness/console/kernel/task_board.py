"""The task board the console server returns for the Web console and the TUI.

The server builds the payload; this module only validates it and gives the TUI plain dataclasses,
like the other kernel snapshot modules. Standard library only: the board screen and its tests can
run without Textual or the server."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .json_shape import json_int, json_list, json_object, json_str


@dataclass(frozen=True)
class BoardSpec:
    """One open spec (epic) and its ticket counters."""

    id: str
    n: int | None
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
    age_seconds: float | None
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
    column_counts: Mapping[str, int] = field(default_factory=dict)


def _dict(value: object, what: str) -> dict[str, object]:
    return json_object(value, f"{what} is not an object")


def _list(value: object, what: str) -> list[object]:
    return json_list(value, f"{what} is not a list")


def _str(value: object, what: str) -> str:
    return json_str(value, f"{what} is not a string")


def _int(value: object, what: str) -> int:
    return json_int(value, f"{what} is not an integer")


def _optional_int(value: object, what: str) -> int | None:
    if value is None:
        return None
    return _int(value, what)


def _optional_str(value: object, what: str) -> str | None:
    if value is None:
        return None
    return _str(value, what)


def _stale(value: object) -> str | None:
    """The server adds a `{reason, message}` object when the tracker read is stale; the TUI only
    needs its human text. Older payloads may carry a plain string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("message", "reason"):
            found = value.get(key)
            if isinstance(found, str) and found.strip():
                return found
    return None


def _optional_number(value: object, what: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} is not a number")
    return float(value)


def _spec(value: object, *, totals: bool) -> BoardSpec:
    found = _dict(value, "spec")
    return BoardSpec(
        id=_str(found.get("id", ""), "spec.id"),
        n=_optional_int(found.get("n"), "spec.n"),
        title=_str(found.get("title", ""), "spec.title"),
        url=_optional_str(found.get("url"), "spec.url"),
        branch=_optional_str(found.get("branch"), "spec.branch"),
        tickets_total=_optional_int(found.get("tickets_total"), "spec.tickets_total")
        or 0
        if totals
        else 0,
        tickets_open=_optional_int(found.get("tickets_open"), "spec.tickets_open") or 0
        if totals
        else 0,
    )


def specs_from_payload(value: object) -> BoardSpecs:
    """The `task_board.specs` payload; `ValueError` when it is outside the schema."""
    found = _dict(value, "specs")
    raw_specs = found.get("specs")
    specs = (
        tuple(_spec(item, totals=True) for item in raw_specs if isinstance(item, dict))
        if isinstance(raw_specs, list)
        else ()
    )
    return BoardSpecs(
        tracker=_str(found.get("tracker", ""), "specs.tracker"),
        specs=specs,
        stale=_stale(found.get("stale")),
        age_seconds=_optional_number(found.get("age_seconds"), "specs.age_seconds"),
        truncated=bool(found.get("truncated", False)),
    )


def _blocker(value: object) -> BoardBlocker:
    found = _dict(value, "blocker")
    state = _str(found.get("state", "unknown"), "blocker.state")
    if state not in {"open", "closed", "unknown"}:
        state = "unknown"
    return BoardBlocker(
        id=_str(found.get("id", ""), "blocker.id"),
        n=_optional_int(found.get("n"), "blocker.n"),
        why=_str(found.get("why", ""), "blocker.why"),
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
    raw_labels = found.get("labels")
    labels = (
        tuple(_str(item, "ticket.labels[]") for item in raw_labels)
        if isinstance(raw_labels, list)
        else ()
    )
    raw_criteria = found.get("criteria")
    criteria = (
        tuple(_str(item, "ticket.criteria[]") for item in raw_criteria)
        if isinstance(raw_criteria, list)
        else ()
    )
    files = []
    raw_files = found.get("files")
    for item in raw_files if isinstance(raw_files, list) else ():
        file = _dict(item, "ticket.files[]")
        files.append(
            (
                _str(file.get("path", ""), "file.path"),
                _str(file.get("why", ""), "file.why"),
            )
        )
    raw_blockers = found.get("blockers")
    blockers = (
        tuple(_blocker(item) for item in raw_blockers)
        if isinstance(raw_blockers, list)
        else ()
    )
    column = _str(found.get("column", "backlog"), "ticket.column")
    if column not in {"backlog", "ready", "progress", "review", "done"}:
        column = "backlog"
    return BoardCard(
        id=_str(found.get("id", ""), "ticket.id"),
        n=_optional_int(found.get("n"), "ticket.n"),
        title=_str(found.get("title", ""), "ticket.title"),
        url=_optional_str(found.get("url"), "ticket.url"),
        closed=bool(found.get("closed", False)),
        column=column,
        labels=labels,
        priority=_optional_str(found.get("priority"), "ticket.priority"),
        sp=_optional_int(found.get("sp"), "ticket.sp"),
        command=_str(found.get("command", ""), "ticket.command"),
        branch=_optional_str(found.get("branch"), "ticket.branch"),
        what=_str(found.get("what", ""), "ticket.what"),
        criteria=criteria,
        files=tuple(files),
        blockers=blockers,
        open_blockers=_optional_int(found.get("open_blockers"), "ticket.open_blockers")
        or 0,
        pr=_pull(found.get("pr")),
        batch=_optional_str(found.get("batch"), "ticket.batch"),
        batch_state=_optional_str(found.get("batch_state"), "ticket.batch_state"),
        dispatch=_optional_str(found.get("dispatch"), "ticket.dispatch"),
        dispatch_state=_optional_str(
            found.get("dispatch_state"), "ticket.dispatch_state"
        ),
        prompt=_str(found.get("prompt", ""), "ticket.prompt"),
        truncated=bool(found.get("truncated", False)),
    )


def board_from_payload(value: object) -> BoardSnapshot:
    """The `task_board.snapshot` payload; `ValueError` when it is outside the schema."""
    found = _dict(value, "board")
    raw_columns = found.get("columns")
    columns = (
        tuple(
            _str(_dict(item, "column").get("id"), "column.id") for item in raw_columns
        )
        if isinstance(raw_columns, list)
        else ()
    )
    counts = (
        {
            _str(_dict(item, "column").get("id"), "column.id"): _optional_int(
                _dict(item, "column").get("count"), "column.count"
            )
            or 0
            for item in raw_columns
        }
        if isinstance(raw_columns, list)
        else {}
    )
    kpis_value = _dict(found.get("kpis", {}), "board.kpis")
    kpis = {
        key: _optional_int(kpis_value.get(key), f"kpis.{key}") or 0
        for key in ("open", "total", "with_open_blockers", "active_batch")
    }
    return BoardSnapshot(
        tracker=_str(found.get("tracker", ""), "board.tracker"),
        ledger=_str(found.get("ledger", "ok"), "board.ledger"),
        spec=_spec(found.get("spec", {}), totals=False),
        columns=columns,
        kpis=kpis,
        tickets=tuple(
            _card(item) for item in _list(found.get("tickets"), "board.tickets")
        ),
        truncated=bool(found.get("truncated", False)),
        column_counts=counts,
    )
