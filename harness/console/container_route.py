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
from dataclasses import dataclass, replace
from datetime import UTC, datetime
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


# ----------------------------------------------------------------------------- Preflight

_STATUS_STATES = {
    "verified": State.OK,
    "unverified": State.BLOCKED,
    "legacy-inherit": State.INFO,
}


def _observed(verification: JsonObject) -> JsonObject:
    """The engine and image facts: the observation when the check passed, else the facts the
    blocked check carried. Nothing here is probed by the console."""
    return {
        **_obj(verification.get("environment")),
        **_obj(verification.get("evidence")),
    }


def _blocker_lines(verification: JsonObject, facts: JsonObject) -> list[str]:
    """Every reason the core gave, verbatim with its remedy; the console classifies none of them."""
    lines: list[str] = []
    for item in _items(facts.get("blockers")):
        reason, remedy = (
            _text(_obj(item).get("reason")),
            _text(_obj(item).get("remedy")),
        )
        if reason:
            lines.append(f"{reason} — {remedy}" if remedy else reason)
    if not lines and _text(verification.get("reason")):
        reason, remedy = (
            _text(verification.get("reason")),
            _text(verification.get("remedy")),
        )
        lines.append(f"{reason} — {remedy}" if remedy else reason)
    return lines


def _check_state(verification: JsonObject, name: str) -> State:
    if name in _items(verification.get("verified")):
        return State.OK
    if name in _items(verification.get("unverified")):
        return State.NOT_CHECKED
    return State.NOT_REPORTED


def _image_rows(facts: JsonObject, probed: bool) -> list[Row]:
    group = "Образы"
    rows: list[Row] = []
    for label, tag_key, id_key in (
        ("Образ worker", "worker_image", "worker_image_id"),
        ("Образ proxy", "proxy_image", "proxy_image_id"),
    ):
        tag = _text(facts.get(tag_key))
        if not tag:
            if label == "Образ proxy":
                rows.append(Row(label, "не задан: sidecar не нужен", State.INFO, group))
            else:
                rows.append(Row(label, "не сообщается", State.NOT_REPORTED, group))
            continue
        image_id = _text(facts.get(id_key))
        if probed and image_id:
            rows.append(Row(label, f"{tag}\n{image_id}", State.OK, group))
        else:
            rows.append(
                Row(
                    label,
                    f"{tag}\nне проверено: образ не наблюдён",
                    State.NOT_CHECKED,
                    group,
                )
            )
    return rows


def preflight_view(result: ApiResult | None, selection: Selection) -> StageView:
    can_check = bool(selection.batch and selection.role)
    recheck = Action(
        "recheck",
        "Перепроверить",
        can_check,
        "" if can_check else NEED_BATCH,
        Effect.OBSERVE,
    )
    notes = (
        "Повторная проверка не запускает worker и не собирает и не скачивает образы: "
        "она только спрашивает у ядра, что наблюдается сейчас.",
    )
    if result is None:
        pending = (
            Row(
                "Preflight",
                "не проверено: проверка ещё не запрашивалась",
                State.NOT_CHECKED,
            ),
        )
        return StageView(Stage.PREFLIGHT, pending, (recheck,), notes=notes)
    if not result.ok:
        failure = _call_failure("Preflight", result)
        return StageView(
            Stage.PREFLIGHT,
            (failure,),
            (recheck,),
            blockers=(result.problem_text or result.outcome.value,),
            notes=notes,
        )
    plan, verification = _packet(result)
    facts = _observed(verification)
    status = _text(verification.get("status"))
    state = _STATUS_STATES.get(status, State.NOT_REPORTED)
    rows = [Row("Статус проверки", status or "не сообщается", state)]
    blockers = _blocker_lines(verification, facts)
    probed = _text(facts.get("engine_mode")) not in ("", "not-probed")
    engine = _text(
        facts.get("engine"), _text(_obj(plan.get("container")).get("engine"))
    )
    rows.append(
        Row(
            "Движок",
            engine or "не сообщается",
            State.OK if probed else State.NOT_CHECKED,
            "Движок",
        )
    )
    rows.append(
        Row(
            "Режим движка",
            _text(facts.get("engine_mode"))
            if probed
            else "не проверено: движок не опрошен",
            State.OK if probed else State.NOT_CHECKED,
            "Движок",
        )
    )
    if "selinux" in facts:
        rows.append(
            Row(
                "SELinux",
                "включён" if facts["selinux"] else "выключен",
                State.INFO,
                "Движок",
            )
        )
    transport = _text(facts.get("transport"))
    rows.append(
        Row(
            "Транспорт",
            transport or "не сообщается",
            State.OK if transport == "external" else State.NOT_REPORTED,
            "Движок",
        )
    )
    rows.extend(_image_rows(facts, probed))
    names = env_names(plan.get("environment"))
    env_state = State.OK if status == "verified" else State.NOT_CHECKED
    rows.append(
        Row(
            "Переменные окружения (имена)",
            ", ".join(names)
            + ("" if status == "verified" else "\nналичие на хосте: не проверено")
            if names
            else "не заданы",
            env_state if names else State.INFO,
            "Окружение",
        )
    )
    requirements = [
        _obj(item)
        for item in _items(_obj(verification.get("required")).get("filesystem"))
    ]
    mounts = "\n".join(
        f"{_text(item.get('resource'))} {_text(item.get('access'))} {_text(item.get('path'))}"
        for item in requirements
    )
    rows.append(
        Row(
            "Монтирования",
            mounts or "не сообщается",
            _check_state(verification, "filesystem") if mounts else State.NOT_REPORTED,
            "Доступ",
        )
    )
    hosts = [
        str(item) for item in _items(_obj(verification.get("required")).get("hosts"))
    ]
    rows.append(
        Row(
            "Сеть",
            ", ".join(hosts) if hosts else "не применимо: хосты не заданы",
            _check_state(verification, "network") if hosts else State.INFO,
            "Доступ",
        )
    )
    if status == "verified":
        rows.append(
            Row(
                "Запуск",
                "preflight пройден; запуск требует отдельного одобрения плана",
                State.INFO,
            )
        )
    else:
        rows.append(
            Row("Запуск", "заблокирован: статус проверки не verified", State.BLOCKED)
        )
    return StageView(Stage.PREFLIGHT, tuple(rows), (recheck,), tuple(blockers), notes)


# ----------------------------------------------------------------------------- Plan / approval


@dataclass(frozen=True)
class Proposal:
    """The one `dispatch propose` the operator may approve. Approval carries exactly this
    `transition_digest`; anything that changed since, or any refusal, sets `stale`."""

    batch: str
    role: str
    runtime: str
    purpose: str
    transition_digest: str
    plan_digest: str
    document: JsonObject
    stale: str = ""


def _requirement_lines(plan: JsonObject) -> str:
    lines = []
    for item in _items(plan.get("requirements")):
        data = _obj(item)
        lines.append(
            f"{_text(data.get('resource'))} {_text(data.get('access'))} {_text(data.get('path'))}"
        )
    return "\n".join(lines)


def plan_view(
    preflight: ApiResult | None,
    proposal: Proposal | None,
    proposal_result: ApiResult | None,
    created: ApiResult | None,
    selection: Selection,
) -> StageView:
    verified = verification_status(preflight) == "verified"
    group = "План"
    rows: list[Row] = []
    blockers: list[str] = []
    document = proposal.document if proposal is not None else None
    if proposal_result is not None and not proposal_result.ok:
        rows.append(_call_failure("Предложение", proposal_result))
        blockers.append(proposal_result.problem_text or proposal_result.outcome.value)
    if document is not None:
        plan = _obj(document.get("runtime_access"))
        container = _obj(plan.get("container"))
        images = _obj(document.get("runtime_images"))
        transition = _obj(document.get("transition"))
        rows.append(
            Row(
                "Монтирования", _requirement_lines(plan) or "не сообщается", None, group
            )
        )
        rows.append(
            Row(
                "Сетевые хосты",
                ", ".join(
                    str(h) for h in _items(_obj(plan.get("network")).get("hosts"))
                )
                or "нет",
                None,
                group,
            )
        )
        rows.append(
            Row(
                "Переменные окружения (имена)",
                ", ".join(env_names(plan.get("environment"))) or "нет",
                None,
                group,
            )
        )
        rows.append(Row("Движок", _text(container.get("engine"), "—"), None, group))
        for label, key in (("Образ worker", "worker"), ("Образ proxy", "proxy")):
            tag = _text(container.get(f"{key}_image"))
            image_id = _text(images.get(key))
            if image_id:
                rows.append(
                    Row(
                        label,
                        f"{tag}\n{image_id}" if tag else image_id,
                        State.OK,
                        group,
                    )
                )
            elif tag:
                rows.append(
                    Row(
                        label,
                        f"{tag}\nне сообщается: digest не закреплён",
                        State.NOT_REPORTED,
                        group,
                    )
                )
        rows.append(
            Row(
                "plan_digest",
                proposal.plan_digest if proposal else "—",
                None,
                "Привязка",
            )
        )
        rows.append(
            Row(
                "transition_digest",
                proposal.transition_digest if proposal else "—",
                State.INFO,
                "Привязка",
            )
        )
        for label, key in (
            ("Следующая роль", "next_role"),
            ("Цель", "purpose"),
            ("Базовый коммит", "base_sha"),
            ("Кандидат", "candidate_sha"),
        ):
            if key in transition:
                rows.append(Row(label, _text(transition[key], "—"), None, "Привязка"))
        if proposal is not None and proposal.stale:
            rows.append(
                Row(
                    "Предложение", f"устарело: {proposal.stale}", State.WARN, "Привязка"
                )
            )
        else:
            rows.append(
                Row(
                    "Одобрение",
                    "привязано к показанному transition_digest; изменение плана, образов, "
                    "кандидата или роли требует нового propose и нового одобрения",
                    State.INFO,
                    "Привязка",
                )
            )
    elif preflight is not None and verified:
        plan, _ = _packet(preflight)
        rows.append(
            Row("Предложение", "не запрошено: выполните propose", State.PENDING)
        )
        rows.append(
            Row(
                "plan_digest (по preflight)",
                _text(plan.get("plan_digest"), "—"),
                State.INFO,
            )
        )
    elif proposal_result is None:
        rows.append(
            Row(
                "Предложение",
                "заблокировано: сначала Preflight со статусом verified",
                State.BLOCKED,
            )
        )
    if created is not None:
        if created.ok:
            doc = created.document or {}
            rows.append(
                Row(
                    "Создан dispatch",
                    _text(doc.get("dispatch_id"), "не сообщается"),
                    State.OK if _text(doc.get("dispatch_id")) else State.NOT_REPORTED,
                    "Результат",
                )
            )
            rows.append(
                Row(
                    "Worker",
                    "не запущен: отправка — отдельное действие",
                    State.INFO,
                    "Результат",
                )
            )
        else:
            rows.append(_call_failure("Создание dispatch", created))
            blockers.append(created.problem_text or created.outcome.value)
    can_propose = bool(selection.batch) and verified
    if not selection.batch:
        propose_reason = NEED_BATCH
    elif not verified:
        propose_reason = "сначала Preflight со статусом verified"
    else:
        propose_reason = ""
    live = proposal is not None and not proposal.stale
    approve_reason = (
        ""
        if live
        else "предложение устарело: выполните propose заново"
        if proposal is not None
        else "сначала запросите предложение (propose)"
    )
    actions = (
        Action(
            "propose",
            "Запросить предложение",
            can_propose,
            propose_reason,
            Effect.RECORD,
        ),
        Action(
            "approve",
            "Одобрить и создать dispatch",
            live,
            approve_reason,
            Effect.APPROVE,
        ),
    )
    return StageView(Stage.PLAN, tuple(rows), actions, tuple(blockers))


# ----------------------------------------------------------------------------- Worker

_LIVENESS = {
    "launching": (State.PENDING, "запускается"),
    "running": (State.OK, "работает по наблюдению runtime"),
    "stopping": (State.WARN, "останавливается"),
    "exited": (State.INFO, "завершён"),
    "lost": (State.WARN, "потерян: runtime не может доказать, чем завершился"),
    "unknown": (State.UNKNOWN, "неизвестно: runtime не знает, работает ли worker"),
}


def worker_entry(result: ApiResult | None, dispatch: str) -> JsonObject | None:
    """The `dispatch status` entry of `dispatch`, if the document reported it."""
    if result is None or not result.ok:
        return None
    for item in _items(_obj(result.document).get("dispatches")):
        entry = _obj(item)
        if _text(entry.get("dispatch_id")) == dispatch:
            return entry
    return None


def _mapping_text(value: object) -> str:
    data = _obj(value)
    return "\n".join(f"{key}: {_text(item)}" for key, item in sorted(data.items()))


def worker_view(result: ApiResult | None, selection: Selection) -> StageView:
    dispatch = selection.dispatch
    ready = bool(dispatch)
    actions = (
        Action(
            "refresh",
            "Обновить: наблюдение, ядро может отреагировать",
            ready,
            "" if ready else "dispatch ещё не создан",
            Effect.OBSERVE,
        ),
        Action(
            "send",
            "Отправить worker (форма dispatch send)",
            ready,
            "" if ready else "dispatch ещё не создан",
            Effect.RUN,
        ),
    )
    notes = (
        "detached-запуск, тишина, exit 0 и отсутствие отчёта не принимают отчёт, не доказывают "
        "остановку и не закрывают задачу: это отдельные факты.",
        "Обновление спрашивает ядро и runtime; ядро может записать реакцию на завершившийся "
        "worker. Автоопроса по таймеру нет.",
    )
    if not ready:
        early = (Row("Worker", "не создан: dispatch ещё не создан", State.PENDING),)
        return StageView(Stage.WORKER, early, actions, notes=notes)
    if result is None:
        early_two = (
            Row("Dispatch", dispatch, State.INFO),
            Row(
                "Состояние",
                "не проверено: статус ещё не запрашивался",
                State.NOT_CHECKED,
            ),
        )
        return StageView(Stage.WORKER, early_two, actions, notes=notes)
    if not result.ok:
        return StageView(
            Stage.WORKER,
            (Row("Dispatch", dispatch, State.INFO), _call_failure("Статус", result)),
            actions,
            (result.problem_text or result.outcome.value,),
            notes,
        )
    document = _obj(result.document)
    if document.get("ledger_busy"):
        busy = Row(
            "Состояние",
            "ledger занят другой операцией: повторите обновление; "
            + _text(document.get("remedy")),
            State.PENDING,
        )
        return StageView(
            Stage.WORKER,
            (Row("Dispatch", dispatch, State.INFO), busy),
            actions,
            notes=notes,
        )
    entry = worker_entry(result, dispatch)
    if entry is None:
        early_three = (
            Row("Dispatch", dispatch, State.INFO),
            Row(
                "Состояние",
                "не сообщается: ядро не вернуло этот dispatch",
                State.NOT_REPORTED,
            ),
        )
        return StageView(Stage.WORKER, early_three, actions, notes=notes)
    execution = _obj(entry.get("execution"))
    launch = _obj(execution.get("launch"))
    exit_ = _obj(execution.get("exit"))
    receipt = _obj(entry.get("adapter_receipt"))
    startup = _obj(entry.get("startup"))
    rows = [
        Row("Dispatch", dispatch, State.INFO, "Dispatch"),
        Row("Роль", _text(entry.get("role"), "не сообщается"), None, "Dispatch"),
        Row(
            "Состояние в ledger",
            _text(entry.get("state"), "не сообщается"),
            None,
            "Dispatch",
        ),
    ]
    launch_id = _text(receipt.get("launch_id")) or _text(
        _obj(execution.get("receipt")).get("launch_id")
    )
    rows.append(
        Row(
            "Receipt / launch_id",
            launch_id or "не сообщается",
            State.OK if launch_id else State.NOT_REPORTED,
            "Запуск",
        )
    )
    engine = _text(execution.get("engine"))
    rows.append(
        Row(
            "Движок",
            engine or "не сообщается",
            None if engine else State.NOT_REPORTED,
            "Запуск",
        )
    )
    images = _mapping_text(launch.get("images"))
    rows.append(
        Row(
            "Образы запуска",
            images or "не сообщается",
            None if images else State.NOT_REPORTED,
            "Запуск",
        )
    )
    if execution:
        state_key = _text(execution.get("state"))
        state, label = _LIVENESS.get(
            state_key, (State.NOT_REPORTED, f"не сообщается: {state_key}")
        )
        rows.append(
            Row("Liveness (inspect)", f"{state_key}: {label}", state, "Наблюдение")
        )
        observed = _text(_obj(execution.get("observation")).get("observed_at"))
        rows.append(
            Row(
                "Наблюдалось",
                observed or "не сообщается",
                None if observed else State.NOT_REPORTED,
                "Наблюдение",
            )
        )
    else:
        rows.append(
            Row(
                "Liveness (inspect)",
                "не сообщается: runtime не наблюдает этот dispatch",
                State.NOT_REPORTED,
                "Наблюдение",
            )
        )
    silent = entry.get("silent_seconds")
    rows.append(
        Row(
            "Тишина worker",
            f"{silent} сек" + ("; stale" if entry.get("stale") else "")
            if silent is not None
            else "не сообщается",
            State.WARN if entry.get("stale") else None,
            "Наблюдение",
        )
    )
    code = exit_.get("exit_code")
    rows.append(
        Row(
            "Код выхода",
            str(code)
            if code is not None
            else "не сообщается: worker не завершился или код не получен",
            State.INFO if code is not None else State.NOT_REPORTED,
            "Завершение",
        )
    )
    for label, key in (
        ("Остановлен кем", "stopped_by"),
        ("OOM", "oom_killed"),
        ("Источник", "source"),
    ):
        if key in exit_:
            rows.append(Row(label, _text(exit_[key]), None, "Завершение"))
    held = entry.get("held_report")
    rows.append(
        Row(
            "Отчёт",
            "удержан: ждёт завершения worker" if held else "не сообщается",
            State.WARN if held else State.NOT_REPORTED,
            "Завершение",
        )
    )
    logs = _text(exit_.get("logs")) or _text(launch.get("logs"))
    rows.append(
        Row(
            "Terminal evidence",
            logs or "не сообщается",
            State.INFO if logs else State.NOT_REPORTED,
            "Завершение",
        )
    )
    if startup:
        rows.append(
            Row(
                "Классификация запуска",
                _text(startup.get("classification"), "не сообщается"),
                None,
                "Запуск",
            )
        )
    reaction = _obj(entry.get("reaction_error"))
    blockers: list[str] = []
    if reaction:
        text = _text(reaction.get("error"))
        remedy = _text(reaction.get("remedy"))
        blockers.append(f"{text} — {remedy}" if remedy else text)
    labels = _mapping_text(launch.get("labels"))
    if labels:
        rows.append(Row("Метки", labels, None, "Запуск"))
    return StageView(Stage.WORKER, tuple(rows), actions, tuple(blockers), notes)


# ----------------------------------------------------------------------------- QA


@dataclass
class QaState:
    """The QA route's own documents: its proposal, its dispatch, its run and the lane."""

    proposal: Proposal | None = None
    proposal_result: ApiResult | None = None
    created: ApiResult | None = None
    run: ApiResult | None = None
    report: JsonObject | None = None
    status: ApiResult | None = None


def _stage_rows(report: JsonObject) -> list[Row]:
    group = "Команды gate"
    rows: list[Row] = []
    stages = _obj(report.get("qa_stages"))
    for index, item in enumerate(_items(stages.get("stages")), start=1):
        stage = _obj(item)
        code = stage.get("exit_code")
        if code is None:
            state, detail = State.NOT_REPORTED, "код выхода не сообщается"
        elif code == 0:
            state, detail = State.OK, "exit_code: 0"
        elif isinstance(code, int) and code < 0:
            state, detail = (
                State.FAILED,
                f"exit_code: {code}: завершена сигналом или прервана",
            )
        else:
            state, detail = State.FAILED, f"exit_code: {code}"
        text = f"{_text(stage.get('command'), '—')}\n{detail}"
        if stage.get("domain"):
            text += f"\ndomain: {_text(stage['domain'])}"
        if stage.get("diagnostics"):
            text += f"\n{_text(stage['diagnostics'])}"
        rows.append(
            Row(f"{index}. {_text(stage.get('stage'), 'stage')}", text, state, group)
        )
    failed = _text(stages.get("failed_stage"))
    if failed:
        rows.append(Row("Остановилась на стадии", failed, State.FAILED, group))
    started = _text(stages.get("code_checks_started"))
    if started:
        rows.append(Row("Проверки кода начаты", started, None, group))
    for item in _items(report.get("checks_run")):
        check = _obj(item)
        result = _text(check.get("result"))
        state = {
            "pass": State.OK,
            "fail": State.FAILED,
            "not_run": State.NOT_CHECKED,
        }.get(result, State.NOT_REPORTED)
        evidence = _text(check.get("evidence"))
        text = _text(check.get("command"), "—") + f"\n{result or 'не сообщается'}"
        if evidence:
            text += f"\n{evidence}"
        rows.append(Row("Проверка", text, state, "Доказательства"))
    return rows


def _lane_rows(status: ApiResult | None) -> list[Row]:
    group = "Lane"
    if status is None:
        return [
            Row(
                "Lane",
                "не проверено: qa status ещё не запрашивался",
                State.NOT_CHECKED,
                group,
            )
        ]
    if not status.ok:
        return [_call_failure("Lane", status)]
    document = _obj(status.document)
    lease = _obj(document.get("lease"))
    queue = _items(document.get("queue"))
    if not lease:
        rows = [Row("Lane", "свободен: активного lease нет", State.OK, group)]
    elif document.get("lease_stale"):
        rows = [
            Row(
                "Lane",
                "lease просрочен: heartbeat владельца не получен\n"
                + _mapping_text(lease),
                State.WARN,
                group,
            )
        ]
    else:
        rows = [Row("Lane", "занят\n" + _mapping_text(lease), State.INFO, group)]
    rows.append(Row("Очередь", str(len(queue)), None, group))
    return rows


def qa_view(qa: QaState, selection: Selection) -> StageView:
    group = "План QA"
    rows: list[Row] = [
        Row(
            "Одобрение",
            "QA — отдельный dispatch роли qa с собственным propose и transition_digest; "
            "одобрение worker не заменяет одобрение QA",
            State.INFO,
            "Привязка",
        )
    ]
    blockers: list[str] = []
    held = qa.proposal
    if qa.proposal_result is not None and not qa.proposal_result.ok:
        rows.append(_call_failure("Предложение QA", qa.proposal_result))
        blockers.append(
            qa.proposal_result.problem_text or qa.proposal_result.outcome.value
        )
    if held is not None:
        plan = _obj(held.document.get("runtime_access"))
        images = _obj(held.document.get("runtime_images"))
        execution = _obj(held.document.get("qa_execution"))
        container = _obj(plan.get("container"))
        rows.append(
            Row(
                "Образ QA",
                _text(container.get("worker_image"), "не сообщается"),
                None,
                group,
            )
        )
        if images.get("worker"):
            rows.append(Row("Digest образа", _text(images["worker"]), State.OK, group))
        rows.append(Row("plan_digest", held.plan_digest or "—", None, "Привязка"))
        rows.append(
            Row("transition_digest", held.transition_digest, State.INFO, "Привязка")
        )
        for label, key in (
            ("Лимит команды, с (по плану)", "command_timeout_seconds"),
            ("Grace остановки, с (по плану)", "stop_grace_seconds"),
        ):
            if key in execution:
                rows.append(Row(label, _text(execution[key]), None, group))
        if held.stale:
            rows.append(
                Row("Предложение", f"устарело: {held.stale}", State.WARN, "Привязка")
            )
    elif qa.proposal_result is None and not selection.qa_dispatch:
        rows.append(
            Row(
                "Предложение QA",
                "не запрошено: выполните propose для роли qa",
                State.PENDING,
            )
        )
    if qa.created is not None:
        if qa.created.ok:
            dispatch = _text(_obj(qa.created.document).get("dispatch_id"))
            rows.append(
                Row(
                    "Создан dispatch QA",
                    dispatch or "не сообщается",
                    State.OK if dispatch else State.NOT_REPORTED,
                    "Результат",
                )
            )
        else:
            rows.append(_call_failure("Создание dispatch QA", qa.created))
            blockers.append(qa.created.problem_text or qa.created.outcome.value)
    if qa.run is not None:
        if not qa.run.ok:
            rows.append(_call_failure("Запуск QA", qa.run))
            blockers.append(qa.run.problem_text or qa.run.outcome.value)
        else:
            document = _obj(qa.run.document)
            rows.append(
                Row(
                    "Состояние QA run",
                    _text(document.get("state"), "не сообщается"),
                    None,
                    "Запуск",
                )
            )
            if document.get("transition_blocked"):
                note = _text(document.get("diagnostic"))
                remedy = _text(document.get("remedy"))
                blockers.append(f"{note} — {remedy}" if remedy else note)
            if document.get("auto_accepted"):
                rows.append(
                    Row(
                        "Автопринятие по политике ядра",
                        "ядро приняло результат",
                        State.INFO,
                        "Запуск",
                    )
                )
            if qa.report is not None:
                rows.extend(_stage_rows(qa.report))
                rows.append(
                    Row(
                        "Исход отчёта",
                        _text(qa.report.get("outcome"), "не сообщается"),
                        None,
                        "Запуск",
                    )
                )
            elif _text(document.get("report")):
                rows.append(
                    Row(
                        "Отчёт",
                        f"не прочитан: {_text(document.get('report'))}",
                        State.NOT_REPORTED,
                        "Запуск",
                    )
                )
        for label in (
            "Контейнер команды",
            "stdout и stderr раздельно",
            "Сигнал, таймаут и grace по факту",
        ):
            rows.append(
                Row(label, "не сообщается ядром", State.NOT_REPORTED, "Не сообщается")
            )
    rows.extend(_lane_rows(qa.status))
    has_batch = bool(selection.batch)
    run_ready = bool(selection.qa_dispatch)
    live = held is not None and not held.stale
    actions = (
        Action(
            "qa-propose",
            "Запросить предложение QA",
            has_batch,
            "" if has_batch else NEED_BATCH,
            Effect.RECORD,
        ),
        Action(
            "qa-approve",
            "Одобрить и создать dispatch QA",
            live,
            ""
            if live
            else "предложение QA устарело: выполните propose заново"
            if held is not None
            else "сначала запросите предложение QA",
            Effect.APPROVE,
        ),
        Action(
            "qa-run",
            "Запустить QA",
            run_ready,
            "" if run_ready else "нужен одобренный dispatch QA",
            Effect.RUN,
        ),
        Action("qa-status", "Состояние lane", True, "", Effect.OBSERVE),
    )
    return StageView(Stage.QA, tuple(rows), actions, tuple(blockers))


# ----------------------------------------------------------------------------- Cleanup

CONTAINER_KINDS = frozenset({"container", "network"})
LIVE_EXECUTION_STATES = frozenset({"launching", "running", "stopping", "unknown"})


@dataclass
class CleanupState:
    """One previewed plan, the digest an apply is bound to, and the last apply's answer."""

    preview: ApiResult | None = None
    plan: JsonObject | None = None
    digest: str = ""
    stale: str = ""  # why the digest can no longer be applied
    apply: ApiResult | None = None


def plan_digest_of(plan: JsonObject) -> str:
    """The digest `harness cleanup --plan-digest` binds an apply to: the core's own function over
    the whole previewed plan, never a console rule."""
    from harness.cleanup import plan_digest

    return plan_digest(plan)  # type: ignore[arg-type]


def _item_dispatch(item: JsonObject) -> str:
    return _text(item.get("dispatch"))


def _is_container_skip(entry: JsonObject) -> bool:
    path = _text(entry.get("path"))
    return path.startswith("harness-") or path == "container resources"


def cleanup_view(
    state: CleanupState, selection: Selection, worker: ApiResult | None
) -> StageView:
    mine = {value for value in (selection.dispatch, selection.qa_dispatch) if value}
    rows: list[Row] = []
    blockers: list[str] = []
    notes = (
        "Живой worker не останавливается: harness его не останавливает, а остановка требует "
        "отдельной явной авторизации вне Cleanup. Чужие ресурсы не удаляются.",
        "Превью строится ядром по меткам этого репозитория для всего репозитория, а не для "
        "одного dispatch; apply удаляет весь показанный план.",
    )
    entry = worker_entry(worker, selection.dispatch) if selection.dispatch else None
    exit_ = _obj(_obj(_obj(entry).get("execution")).get("exit"))
    live = (
        _text(_obj(_obj(entry).get("execution")).get("state")) in LIVE_EXECUTION_STATES
    )
    evidence = _text(exit_.get("logs"))
    rows.append(
        Row(
            "Сохранённые доказательства (execution.exit)",
            f"код выхода: {_text(exit_.get('exit_code'), 'не сообщается')}\n{evidence}"
            if exit_
            else "не сообщается: обновите Worker, чтобы получить execution.exit",
            State.INFO if exit_ else State.NOT_REPORTED,
            "Доказательства",
        )
    )
    if live:
        rows.append(
            Row(
                "Worker текущего dispatch",
                "жив или неизвестен по runtime: он не будет остановлен и не будет удалён",
                State.WARN,
                "Доказательства",
            )
        )
    plan = state.plan
    removable = 0
    if state.preview is None:
        rows.append(Row("Превью", "не запрошено: выполните превью", State.NOT_CHECKED))
    elif not state.preview.ok:
        rows.append(_call_failure("Превью", state.preview))
        blockers.append(state.preview.problem_text or state.preview.outcome.value)
    elif plan is None:
        rows.append(
            Row("Превью", "не сообщается: ядро не вернуло план", State.NOT_REPORTED)
        )
    else:
        items = [_obj(item) for item in _items(plan.get("remove"))]
        containers = [
            item for item in items if _text(item.get("kind")) in CONTAINER_KINDS
        ]
        others = [
            item for item in items if _text(item.get("kind")) not in CONTAINER_KINDS
        ]
        removable = len(items)
        group = "План (весь репозиторий)"
        rows.append(Row("Режим", _text(plan.get("mode"), "—"), None, group))
        rows.append(
            Row(
                "К удалению",
                f"{len(items)}: контейнеры и сети {len(containers)}, прочее {len(others)}",
                State.INFO,
                group,
            )
        )
        for item in containers:
            owned = _item_dispatch(item) in mine
            rows.append(
                Row(
                    "Контейнер" if _text(item.get("kind")) == "container" else "Сеть",
                    f"{_text(item.get('path'))}\n{_text(item.get('engine'))} {_text(item.get('engine_id'))}\n"
                    f"dispatch {_item_dispatch(item) or '—'}"
                    + ("; текущий dispatch" if owned else ""),
                    State.INFO,
                    group,
                )
            )
        kinds: dict[str, int] = {}
        for item in others:
            kind = _text(item.get("kind"), "—")
            kinds[kind] = kinds.get(kind, 0) + 1
        if others:
            rows.append(
                Row(
                    "Не контейнерные пункты того же плана",
                    f"{len(others)}: "
                    + ", ".join(
                        f"{kind} {count}" for kind, count in sorted(kinds.items())
                    ),
                    State.WARN,
                    group,
                )
            )
        skipped = [_obj(item) for item in _items(plan.get("skipped"))]
        protected = [item for item in skipped if _is_container_skip(item)]
        for item in protected:
            rows.append(
                Row(
                    "Защищён",
                    f"{_text(item.get('path'))}\n{_text(item.get('reason'), 'причина не сообщается')}",
                    State.WARN,
                    "Защищённые ресурсы",
                )
            )
        if len(skipped) > len(protected):
            rows.append(
                Row(
                    "Прочие пропущенные пункты",
                    str(len(skipped) - len(protected)),
                    None,
                    "Защищённые ресурсы",
                )
            )
        if state.digest:
            rows.append(Row("plan-digest", state.digest, State.INFO, "Привязка"))
        if state.stale:
            rows.append(
                Row("Превью", f"устарело: {state.stale}", State.WARN, "Привязка")
            )
    if state.apply is not None:
        group = "Результат применения"
        if state.apply.documents:
            result = _obj(state.apply.section("result"))
            removed = [str(item) for item in _items(result.get("removed"))]
            failed = [_obj(item) for item in _items(result.get("failed"))]
            rows.append(
                Row(
                    "Удалено",
                    f"{len(removed)}\n" + "\n".join(removed),
                    State.OK if removed else State.INFO,
                    group,
                )
            )
            for item in failed:
                rows.append(
                    Row(
                        "Не удалось",
                        f"{_text(item.get('path'))}\n{_text(item.get('reason'))}",
                        State.FAILED,
                        group,
                    )
                )
        if not state.apply.ok:
            if not state.apply.documents:
                rows.append(_call_failure("Применение", state.apply))
            blockers.append(state.apply.problem_text or state.apply.outcome.value)
    protects_evidence = (
        bool(selection.dispatch)
        and bool(plan)
        and any(
            _item_dispatch(_obj(item)) == selection.dispatch
            for item in _items(_obj(plan).get("remove"))
        )
    )
    if not state.digest:
        apply_reason = "сначала выполните превью"
    elif state.stale:
        apply_reason = "превью устарело: выполните его заново"
    elif removable == 0:
        apply_reason = "в плане нечего удалять"
    elif protects_evidence and not exit_:
        apply_reason = "доказательства worker не сохранены: обновите Worker до удаления его ресурсов"
    else:
        apply_reason = ""
    can_apply = not apply_reason
    actions = (
        Action("cleanup-preview", "Превью очистки", True, "", Effect.OBSERVE),
        Action(
            "cleanup-apply",
            "Применить показанный план",
            can_apply,
            apply_reason,
            Effect.DELETE,
        ),
    )
    return StageView(Stage.CLEANUP, tuple(rows), actions, tuple(blockers), notes)


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
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(
            timespec="seconds"
        ),
    ) -> None:
        self.repo = repo
        self.api = api or CoordinatorApi(repo, runner)
        self._load_authored = load_authored
        self._load_report = load_report
        self._now = now
        self.selection = Selection()
        self.preflight: ApiResult | None = None
        self.proposal: Proposal | None = None
        self.proposal_result: ApiResult | None = None
        self.created: ApiResult | None = None
        self.worker: ApiResult | None = None
        self.qa = QaState()
        self.cleanup = CleanupState()

    def select(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> None:
        """Choose the batch, role and runtime; a different choice drops what belonged to the old."""
        chosen = (batch.strip(), role.strip() or "developer", runtime.strip())
        current = (self.selection.batch, self.selection.role, self.selection.runtime)
        if chosen != current:
            same_batch = chosen[0] == self.selection.batch
            self.selection = Selection(
                *chosen,
                dispatch=self.selection.dispatch if same_batch else "",
                qa_dispatch=self.selection.qa_dispatch if same_batch else "",
            )
            self.preflight = None
            self.proposal = None
            self.proposal_result = None
            self.created = None
            self.worker = None
            self.qa = QaState()
            self.cleanup = CleanupState()

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
        self._detect_drift()
        return self.preflight

    def _detect_drift(self) -> None:
        """A held proposal no longer matches a plan the core now reports: it needs a new propose."""
        held = self.proposal
        if held is None or held.stale:
            return
        plan, _ = _packet(self.preflight)
        if verification_status(self.preflight) != "verified":
            reason = "preflight больше не verified"
        elif _text(plan.get("plan_digest")) != held.plan_digest:
            reason = "plan_digest изменился после propose"
        else:
            return
        self.proposal = replace(
            held, stale=f"{reason}: нужны новый propose и новое одобрение"
        )

    def _dispatch_values(self, held: Proposal) -> dict[str, str]:
        values = {"batch": held.batch, "role": held.role, "purpose": held.purpose}
        if held.runtime:
            values["runtime"] = held.runtime
        return values

    def _propose(self, role: str) -> tuple[Proposal | None, ApiResult]:
        """One `dispatch propose` for `role`; the proposal is held only with a transition digest."""
        values = {
            "batch": self.selection.batch,
            "role": role,
            "purpose": "work",
        }
        if self.selection.runtime:
            values["runtime"] = self.selection.runtime
        result = self.api.call(("dispatch", "propose"), values)
        document = result.document if result.ok else None
        digest = _text(_obj(document).get("transition_digest"))
        if document is None or not digest:
            return None, result
        plan = _obj(document.get("runtime_access"))
        held = Proposal(
            self.selection.batch,
            role,
            self.selection.runtime,
            "work",
            digest,
            _text(plan.get("plan_digest")),
            document,
        )
        return held, result

    def _approve(self, held: Proposal, approved_by: str) -> ApiResult:
        """`dispatch create` carrying only the digest of the proposal that was displayed."""
        approver = approved_by.strip()
        if not approver:
            raise ValueError("approved_by is required")
        values = {
            **self._dispatch_values(held),
            "approved_by": approver,
            "approved_at": self._now(),
            "transition_digest": held.transition_digest,
        }
        return self.api.call(("dispatch", "create"), values)

    def propose(self) -> ApiResult:
        """`dispatch propose`: the core records a proposal; nothing is approved or started. It runs
        only after a verified preflight, so a blocked route never reaches an approval."""
        if verification_status(self.preflight) != "verified":
            raise PermissionError("dispatch propose requires a verified preflight")
        self.created = None
        held, result = self._propose(self.selection.role)
        self.proposal, self.proposal_result = (
            held,
            result,
        )  # any outcome replaces the held one
        return result

    def create(self, approved_by: str) -> ApiResult:
        """`dispatch create` with the explicit approval bound to the held proposal's own
        `transition_digest`. Any outcome consumes the proposal: a refusal makes it stale and a
        success is not repeatable, so a drifted transition always needs a new propose."""
        held = self.proposal
        if held is None or held.stale:
            raise PermissionError("no live proposal to approve")
        result = self._approve(held, approved_by)
        self.created = result
        if result.ok:
            dispatch = _text(_obj(result.document).get("dispatch_id"))
            if dispatch:
                self.selection.dispatch = dispatch
            self.proposal = None
        else:
            self.proposal = replace(
                held,
                stale="отказ ядра: " + (result.problem_text or result.outcome.value),
            )
        return result

    def propose_qa(self) -> ApiResult:
        """`dispatch propose --role qa`: QA's own proposal and digest, never the worker's."""
        if not self.selection.batch:
            raise PermissionError("no batch selected")
        self.qa.created = None
        held, result = self._propose("qa")
        self.qa.proposal, self.qa.proposal_result = held, result
        return result

    def create_qa(self, approved_by: str) -> ApiResult:
        """The explicit approval of the QA proposal, bound to its own transition digest."""
        held = self.qa.proposal
        if held is None or held.stale:
            raise PermissionError("no live QA proposal to approve")
        result = self._approve(held, approved_by)
        self.qa.created = result
        if result.ok:
            dispatch = _text(_obj(result.document).get("dispatch_id"))
            if dispatch:
                self.selection.qa_dispatch = dispatch
            self.qa.proposal = None
        else:
            self.qa.proposal = replace(
                held,
                stale="отказ ядра: " + (result.problem_text or result.outcome.value),
            )
        return result

    def run_qa(self) -> ApiResult:
        """`qa run --dispatch`: gates run in a container. It needs the QA dispatch, which only
        its own approval creates; a worker approval never reaches this."""
        if not self.selection.qa_dispatch:
            raise PermissionError("no approved QA dispatch")
        result = self.api.call(("qa", "run"), {"dispatch": self.selection.qa_dispatch})
        self.qa.run = result
        path = _text(_obj(result.document).get("report")) if result.ok else ""
        self.qa.report = self._load_report(path) if path else None
        return result

    def refresh_qa(self) -> ApiResult:
        """`qa status`: the lane lease and queue, read-only."""
        self.qa.status = self.api.call(("qa", "status"))
        return self.qa.status

    def preview_cleanup(self) -> ApiResult:
        """`harness cleanup <repo>` without --apply: a plan for the whole repository; it removes
        nothing. Its digest is what a later apply is bound to."""
        result = self.api.cleanup()
        plan = _obj(result.section("plan")) if result.ok else {}
        self.cleanup = CleanupState(
            preview=result,
            plan=plan or None,
            digest=plan_digest_of(plan) if plan else "",
        )
        return result

    def apply_cleanup(self) -> ApiResult:
        """`--apply --plan-digest <digest of the previewed plan>`: any outcome spends the digest,
        so a changed plan or a refusal always needs a new preview."""
        state = self.cleanup
        if not state.digest or state.stale:
            raise PermissionError("no live cleanup preview to apply")
        result = self.api.cleanup(apply_digest=state.digest)
        state.apply = result
        state.stale = "применение выполнено или отклонено: нужно новое превью"
        return result

    def refresh_worker(self) -> ApiResult:
        """`dispatch status --dispatch`: not read-only, since the core may react to an ended
        execution; it runs only on the operator's explicit button, never from a timer or a tab."""
        if not self.selection.dispatch:
            raise PermissionError("no worker dispatch to observe")
        self.worker = self.api.call(
            ("dispatch", "status"), {"dispatch": self.selection.dispatch}
        )
        return self.worker

    def executor_context(self) -> tuple[tuple[str, str], ...]:
        """Worker, QA and the engine labels for the strip above the tabs; never a secret."""
        selection = self.selection
        entry = worker_entry(self.worker, selection.dispatch) or {}
        labels = _mapping_text(
            _obj(_obj(entry.get("execution")).get("launch")).get("labels")
        )
        return (
            ("Worker", selection.dispatch or "не создан"),
            ("QA", selection.qa_dispatch or "не создан"),
            ("Метки", labels.replace("\n", ", ") or "не сообщаются"),
        )

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
        title = STAGE_TITLES[Stage.PLAN]
        if self.created is not None and self.created.ok:
            plan = Tab(Stage.PLAN, title, State.OK, "dispatch создан")
        elif self.proposal is not None and self.proposal.stale:
            plan = Tab(Stage.PLAN, title, State.WARN, self.proposal.stale)
        elif self.proposal is not None:
            plan = Tab(Stage.PLAN, title, State.PENDING, "предложение ждёт одобрения")
        else:
            plan = Tab(Stage.PLAN, title, State.PENDING, "предложение не запрашивалось")
        if not verified and self.proposal is None and self.created is None:
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
        if selection.dispatch:
            worker = Tab(
                Stage.WORKER, STAGE_TITLES[Stage.WORKER], *self._worker_tab_state()
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
        if selection.batch and self.qa.run is not None:
            qa = Tab(Stage.QA, STAGE_TITLES[Stage.QA], *self._qa_tab_state())
        elif selection.batch and selection.qa_dispatch:
            qa = Tab(
                Stage.QA,
                STAGE_TITLES[Stage.QA],
                State.PENDING,
                "dispatch QA создан, QA не запускался",
            )
        cleanup = Tab(
            Stage.CLEANUP,
            STAGE_TITLES[Stage.CLEANUP],
            State.INFO,
            "превью не запрашивалось",
        )
        if self.cleanup.preview is not None and not self.cleanup.preview.ok:
            cleanup = Tab(
                Stage.CLEANUP,
                STAGE_TITLES[Stage.CLEANUP],
                State.FAILED,
                self.cleanup.preview.problem_text,
            )
        elif self.cleanup.preview is not None:
            cleanup = Tab(
                Stage.CLEANUP,
                STAGE_TITLES[Stage.CLEANUP],
                State.INFO,
                "превью получено",
            )
        setup = Tab(Stage.SETUP, STAGE_TITLES[Stage.SETUP], State.INFO)
        return (setup, pre, plan, worker, qa, cleanup)

    def _qa_tab_state(self) -> tuple[State, str]:
        run = self.qa.run
        if run is None or not run.ok:
            return State.FAILED, (run.problem_text if run is not None else "")
        stages = _obj(_obj(self.qa.report).get("qa_stages"))
        if self.qa.report is None:
            return State.NOT_REPORTED, "отчёт QA не прочитан"
        if _text(stages.get("failed_stage")):
            return (
                State.FAILED,
                f"остановилась на стадии {_text(stages.get('failed_stage'))}",
            )
        if any(
            _obj(item).get("result") == "fail"
            for item in _items(self.qa.report.get("checks_run"))
        ):
            return State.FAILED, "есть проваленная проверка"
        if any(
            _obj(item).get("result") == "not_run"
            for item in _items(self.qa.report.get("checks_run"))
        ):
            return State.NOT_CHECKED, "часть проверок не выполнена"
        return State.OK, ""

    def _worker_tab_state(self) -> tuple[State, str]:
        if self.worker is None:
            return State.NOT_CHECKED, "статус ещё не запрашивался"
        if not self.worker.ok:
            return State.FAILED, self.worker.problem_text or self.worker.outcome.value
        entry = worker_entry(self.worker, self.selection.dispatch)
        execution = _obj(_obj(entry).get("execution"))
        if not execution:
            return State.NOT_REPORTED, ""
        state, label = _LIVENESS.get(
            _text(execution.get("state")), (State.NOT_REPORTED, "")
        )
        return state, label

    def view(self, stage: Stage) -> StageView:
        if stage is Stage.SETUP:
            return setup_view(
                self._load_authored(self.repo), self.preflight, self.selection
            )
        if stage is Stage.PREFLIGHT:
            return preflight_view(self.preflight, self.selection)
        if stage is Stage.CLEANUP:
            return cleanup_view(self.cleanup, self.selection, self.worker)
        if stage is Stage.QA:
            return qa_view(self.qa, self.selection)
        if stage is Stage.WORKER:
            return worker_view(self.worker, self.selection)
        if stage is Stage.PLAN:
            return plan_view(
                self.preflight,
                self.proposal,
                self.proposal_result,
                self.created,
                self.selection,
            )
        raise KeyError(stage)
