"""The route's model: stages, states, rows, actions, views and tabs, with the helpers every
stage view shares."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..coordinator_api import ApiResult, Outcome
from ..json_fields import items_or_empty


JsonObject = dict[str, object]


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


class Stage(str, Enum):
    SETUP = "setup"
    PREFLIGHT = "preflight"
    PLAN = "plan"
    WORKER = "worker"
    QA = "qa"
    CLEANUP = "cleanup"


STAGE_TITLES: dict[Stage, str] = {
    Stage.SETUP: "Setup",
    Stage.PREFLIGHT: "Preflight",
    Stage.PLAN: "Plan / approval",
    Stage.WORKER: "Worker",
    Stage.QA: "QA",
    Stage.CLEANUP: "Cleanup",
}


class State(str, Enum):
    """Status as icon plus label, never colour alone."""

    OK = "ok"
    INFO = "info"
    WARN = "warn"
    BLOCKED = "blocked"
    FAILED = "failed"
    PENDING = "pending"
    NOT_CHECKED = "not-checked"
    NOT_REPORTED = "not-reported"
    UNKNOWN = "unknown"


STATE_MARKS: dict[State, tuple[str, str]] = {
    State.OK: ("✔", "ок"),
    State.INFO: ("·", ""),
    State.WARN: ("⚠", "внимание"),
    State.BLOCKED: ("✖", "заблокировано"),
    State.FAILED: ("✖", "сбой"),
    State.PENDING: ("…", "ожидается"),
    State.NOT_CHECKED: ("○", "не проверено"),
    State.NOT_REPORTED: ("○", "не сообщается"),
    State.UNKNOWN: ("?", "неизвестно"),
}


def mark(state: State) -> str:
    """`✔ ок`, `○ не проверено`: the icon and its label."""
    icon, label = STATE_MARKS[state]
    return f"{icon} {label}".strip()


class Effect(str, Enum):
    """What an action does outside the console, so a screen knows whether to confirm it."""

    READ = "read"  # opens a view or an editor; changes nothing
    OBSERVE = (
        "observe"  # a read-only call; the core may still react to what it observes
    )
    RECORD = "record"  # the core writes its own record (a proposal)
    APPROVE = "approve"  # binds an approval to a displayed transition
    RUN = "run"  # runs gates in a container
    DELETE = "delete"  # removes resources by a previewed plan


CONFIRMED_EFFECTS = frozenset({Effect.APPROVE, Effect.RUN, Effect.DELETE})


@dataclass(frozen=True)
class Row:
    """One labelled fact. `value` is never shortened: a screen wraps and scrolls it."""

    label: str
    value: str = ""
    state: State | None = None
    group: str = ""


@dataclass(frozen=True)
class Action:
    key: str
    label: str
    enabled: bool = True
    reason: str = ""  # why a disabled action cannot run; visible beside it
    effect: Effect = Effect.READ

    @property
    def needs_confirmation(self) -> bool:
        return self.effect in CONFIRMED_EFFECTS


@dataclass(frozen=True)
class StageView:
    stage: Stage
    rows: tuple[Row, ...] = ()
    actions: tuple[Action, ...] = ()
    blockers: tuple[str, ...] = ()  # verbatim reasons that stop the route, shown first
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tab:
    stage: Stage
    title: str
    state: State
    reason: str = ""


@dataclass
class Selection:
    """What the operator chose; a change drops every result that belonged to the old choice."""

    batch: str = ""
    role: str = "developer"
    runtime: str = ""
    dispatch: str = ""  # the worker dispatch, once created
    qa_dispatch: str = ""  # the separate role=qa dispatch


NEED_BATCH = "выберите batch и роль"


def env_names(value: object) -> list[str]:
    """Environment variable names only: a stray `NAME=value` or a mapping loses its values here."""
    if isinstance(value, dict):
        return sorted(str(name) for name in value)
    return [str(item).split("=", 1)[0] for item in items_or_empty(value)]


def _call_failure(label: str, result: ApiResult) -> Row:
    """An honest row for a call that gave no document: its own text, not a guess."""
    state = State.FAILED if result.outcome is not Outcome.REFUSED else State.BLOCKED
    detail = result.problem_text or f"выход {result.returncode}"
    return Row(label, f"{result.outcome.value}: {detail}", state)
