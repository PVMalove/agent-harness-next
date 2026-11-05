"""View-model of the container executor route: six stages (Setup, Preflight, Plan / approval, Worker,
QA, Cleanup) over the structured coordinator client. Textual-free like the rest of the console seam.

The model owns no rule of the core: every fact comes from a document the coordinator CLI printed
(`dispatch preflight`, `propose`, `create`, `status`, `qa run`/`status`, `harness cleanup`), shown as it
is. What the core did not report is shown as `не проверено` or `не сообщается`, never as a success.
Choosing a stage only selects which view is drawn; each external effect is an `Action` a screen
runs on an explicit button, and an action that cannot run carries its visible `reason`. Environment
variables appear by name only; no value ever reaches a row, an argv or a log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from .coordinator_api import ApiResult, CoordinatorApi, Outcome
from .runner import CommandRunner, capturing_runner

JsonObject = dict[str, object]


def _obj(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


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


@dataclass(frozen=True)
class Authored:
    """The authored `.harness/orchestration.json`, read-only; a problem is shown, never hidden."""

    document: JsonObject | None
    problem: str = ""


def read_authored(repo: Path) -> Authored:
    path = repo / ".harness" / "orchestration.json"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return Authored(None, f"конфигурация не прочитана: {exc.strerror or exc}")
    try:
        document = json.loads(text)
    except ValueError:
        return Authored(None, "конфигурация не разбирается как JSON")
    if not isinstance(document, dict):
        return Authored(None, "конфигурация не является объектом JSON")
    return Authored(document)


def env_names(value: object) -> list[str]:
    """Environment variable names only: a stray `NAME=value` or a mapping loses its values here."""
    if isinstance(value, dict):
        return sorted(str(name) for name in value)
    return [str(item).split("=", 1)[0] for item in _items(value)]


def _call_failure(label: str, result: ApiResult) -> Row:
    """An honest row for a call that gave no document: its own text, not a guess."""
    state = State.FAILED if result.outcome is not Outcome.REFUSED else State.BLOCKED
    detail = result.problem_text or f"выход {result.returncode}"
    return Row(label, f"{result.outcome.value}: {detail}", state)


def _packet(result: ApiResult | None) -> tuple[JsonObject, JsonObject]:
    """The effective access plan and its verification from a `dispatch preflight` document."""
    document = result.document if result is not None and result.ok else None
    runtime_access = _obj(
        _obj(_obj(document).get("decision_packet")).get("runtime_access")
    )
    return _obj(runtime_access.get("plan")), _obj(runtime_access.get("verification"))


def verification_status(result: ApiResult | None) -> str:
    """The `status` of the preflight verification block, or `` `` when none was reported."""
    return _text(_packet(result)[1].get("status"))


def preflight_tab_state(result: ApiResult | None) -> tuple[State, str]:
    if result is None:
        return State.NOT_CHECKED, "не запрашивалось"
    if not result.ok:
        state = State.BLOCKED if result.outcome is Outcome.REFUSED else State.FAILED
        return state, result.problem_text or result.outcome.value
    status = verification_status(result)
    if status == "verified":
        return State.OK, ""
    if status == "unverified":
        return State.BLOCKED, _text(_packet(result)[1].get("reason"))
    if status == "legacy-inherit":
        return State.INFO, "наследование без контейнера"
    return State.NOT_REPORTED, ""


# ----------------------------------------------------------------------------- Setup


def _component_rows(group: str, component: object) -> list[Row]:
    data = _obj(component)
    rows: list[Row] = []
    if "mode" in data:
        rows.append(Row("Режим", _text(data["mode"]), None, group))
    container = _obj(data.get("container"))
    if container:
        rows.append(
            Row(
                "Движок",
                _text(container.get("engine"), "docker (по умолчанию)"),
                None,
                group,
            )
        )
        rows.append(
            Row("Образ worker", _text(container.get("worker_image"), "—"), None, group)
        )
        rows.append(
            Row(
                "Образ proxy",
                _text(container.get("proxy_image"), "не задан"),
                None,
                group,
            )
        )
    if "environment" in data:
        names = env_names(data["environment"])
        rows.append(
            Row("Переменные окружения (имена)", ", ".join(names) or "нет", None, group)
        )
    hosts = [str(item) for item in _items(_obj(data.get("network")).get("hosts"))]
    if "network" in data:
        rows.append(Row("Сетевые хосты", ", ".join(hosts) or "нет", None, group))
    return rows


def authored_rows(authored: Authored) -> list[Row]:
    if authored.document is None:
        return [Row("Авторская конфигурация", authored.problem, State.FAILED)]
    extension = _text(
        _obj(authored.document.get("extensions")).get("runtime_access"), "none"
    )
    rows = [
        Row(
            "extensions.runtime_access",
            extension,
            State.OK if extension == "docker" else State.WARN,
        )
    ]
    if extension != "docker":
        rows.append(
            Row(
                "Контейнерный исполнитель",
                "не включён: worker не будет запущен в контейнере",
                State.WARN,
            )
        )
    policy = _obj(authored.document.get("access_policy"))
    if not policy:
        rows.append(Row("access_policy", "не задана", State.INFO))
    rows.extend(_component_rows("access_policy.defaults", policy.get("defaults")))
    for section in ("roles", "operations"):
        for name, component in sorted(_obj(policy.get(section)).items()):
            rows.extend(_component_rows(f"access_policy.{section}.{name}", component))
    return rows


def _plan_rows(plan: JsonObject) -> list[Row]:
    group = "Эффективный план"
    container = _obj(plan.get("container"))
    rows = [
        Row("Режим", _text(plan.get("mode"), "—"), None, group),
        Row("Движок", _text(container.get("engine"), "—"), None, group),
        Row("Образ worker", _text(container.get("worker_image"), "—"), None, group),
        Row(
            "Образ proxy", _text(container.get("proxy_image"), "не задан"), None, group
        ),
        Row(
            "Переменные окружения (имена)",
            ", ".join(env_names(plan.get("environment"))) or "нет",
            None,
            group,
        ),
        Row(
            "Сетевые хосты",
            ", ".join(
                str(item) for item in _items(_obj(plan.get("network")).get("hosts"))
            )
            or "нет",
            None,
            group,
        ),
        Row("plan_digest", _text(plan.get("plan_digest"), "—"), None, group),
    ]
    sources = _obj(plan.get("sources"))
    for key, source in sorted(sources.items()):
        text = _text(source)
        rows.append(Row("Источник", f"{key}: {text}", None, group))
        if text.startswith(("roles.", "operations.")):
            rows.append(
                Row(
                    "Переопределение заменяет слой целиком",
                    f"{key}: {text}",
                    State.WARN,
                    group,
                )
            )
    return rows


def setup_view(
    authored: Authored, preflight: ApiResult | None, selection: Selection
) -> StageView:
    rows = authored_rows(authored)
    plan, _ = _packet(preflight)
    if preflight is None:
        rows.append(
            Row(
                "Эффективный план",
                "не проверено: выберите batch и роль и выполните Preflight"
                if not selection.batch
                else "не проверено: выполните Preflight",
                State.NOT_CHECKED,
            )
        )
    elif not preflight.ok:
        rows.append(_call_failure("Эффективный план", preflight))
    elif plan:
        rows.extend(_plan_rows(plan))
    else:
        rows.append(Row("Эффективный план", "не сообщается", State.NOT_REPORTED))
    can_refresh = bool(selection.batch and selection.role)
    actions = (
        Action("edit-config", "Изменить в мастере настройки"),
        Action(
            "recheck",
            "Обновить эффективный план",
            can_refresh,
            "" if can_refresh else NEED_BATCH,
            Effect.OBSERVE,
        ),
    )
    notes = (
        "Запись идёт только через мастер настройки: черновик, проверка, diff, подтверждение, "
        "резервная копия. Сохранение не запускает worker.",
    )
    return StageView(Stage.SETUP, tuple(rows), actions, notes=notes)


# ----------------------------------------------------------------------------- Session


def read_report(path: str) -> JsonObject | None:
    """A completion report file the core named; unreadable means `None`, never a guess."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


class RouteSession:
    """The operator's selection and the last document of every stage. All process work goes
    through the injected client; no method here starts a worker on its own."""

    def __init__(
        self,
        repo: Path,
        runner: CommandRunner = capturing_runner,
        *,
        api: CoordinatorApi | None = None,
        load_authored: Callable[[Path], Authored] = read_authored,
        load_report: Callable[[str], JsonObject | None] = read_report,
    ) -> None:
        self.repo = repo
        self.api = api or CoordinatorApi(repo, runner)
        self._load_authored = load_authored
        self._load_report = load_report
        self.selection = Selection()
        self.preflight: ApiResult | None = None

    def select(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> None:
        """Choose the batch, role and runtime; a different choice drops what belonged to the old."""
        chosen = (batch.strip(), role.strip() or "developer", runtime.strip())
        current = (self.selection.batch, self.selection.role, self.selection.runtime)
        if chosen != current:
            self.selection = Selection(*chosen)
            self.preflight = None

    def _preflight_values(self) -> dict[str, str]:
        values = {"batch": self.selection.batch, "role": self.selection.role}
        if self.selection.runtime:
            values["runtime"] = self.selection.runtime
        return values

    def recheck(self) -> ApiResult:
        """`dispatch preflight`: read-only for the executor; it builds and pulls nothing."""
        self.preflight = self.api.call(
            ("dispatch", "preflight"), self._preflight_values()
        )
        return self.preflight

    def tabs(self) -> tuple[Tab, ...]:
        """Every stage with its state and the reason it cannot proceed. A tab stays selectable:
        choosing it only draws its view, so availability is shown, never enforced by hiding."""
        selection = self.selection
        verified = verification_status(self.preflight) == "verified"
        if not selection.batch:
            pre = Tab(
                Stage.PREFLIGHT,
                STAGE_TITLES[Stage.PREFLIGHT],
                State.NOT_CHECKED,
                NEED_BATCH,
            )
        else:
            pre = Tab(
                Stage.PREFLIGHT,
                STAGE_TITLES[Stage.PREFLIGHT],
                *preflight_tab_state(self.preflight),
            )
        plan = Tab(Stage.PLAN, STAGE_TITLES[Stage.PLAN], State.PENDING, "")
        if not verified:
            plan = Tab(
                Stage.PLAN,
                STAGE_TITLES[Stage.PLAN],
                State.BLOCKED,
                "сначала Preflight со статусом verified",
            )
        worker = Tab(
            Stage.WORKER,
            STAGE_TITLES[Stage.WORKER],
            State.PENDING,
            "dispatch ещё не создан",
        )
        qa = (
            Tab(Stage.QA, STAGE_TITLES[Stage.QA], State.NOT_CHECKED, NEED_BATCH)
            if not selection.batch
            else Tab(
                Stage.QA,
                STAGE_TITLES[Stage.QA],
                State.PENDING,
                "отдельный dispatch роли qa ещё не создан",
            )
        )
        cleanup = Tab(
            Stage.CLEANUP,
            STAGE_TITLES[Stage.CLEANUP],
            State.INFO,
            "превью не запрашивалось",
        )
        setup = Tab(Stage.SETUP, STAGE_TITLES[Stage.SETUP], State.INFO)
        return (setup, pre, plan, worker, qa, cleanup)

    def view(self, stage: Stage) -> StageView:
        if stage is Stage.SETUP:
            return setup_view(
                self._load_authored(self.repo), self.preflight, self.selection
            )
        raise KeyError(stage)
