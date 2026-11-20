"""The Preflight stage: the effective access plan and its verification from
`dispatch preflight`."""

from __future__ import annotations


from ..coordinator_api import ApiResult, Outcome
from ..json_fields import items_or_empty
from ..json_fields import mapping_or_empty
from .model import (
    NEED_BATCH,
    Action,
    Effect,
    JsonObject,
    Row,
    Selection,
    Stage,
    StageView,
    State,
    _call_failure,
    _text,
    env_names,
)


def _packet(result: ApiResult | None) -> tuple[JsonObject, JsonObject]:
    """The effective access plan and its verification from a `dispatch preflight` document."""
    document = result.document if result is not None and result.ok else None
    runtime_access = mapping_or_empty(
        mapping_or_empty(mapping_or_empty(document).get("decision_packet")).get(
            "runtime_access"
        )
    )
    return mapping_or_empty(runtime_access.get("plan")), mapping_or_empty(
        runtime_access.get("verification")
    )


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


_STATUS_STATES = {
    "verified": State.OK,
    "unverified": State.BLOCKED,
    "legacy-inherit": State.INFO,
}


def _observed(verification: JsonObject) -> JsonObject:
    """The engine and image facts: the observation when the check passed, else the facts the
    blocked check carried. Nothing here is probed by the console."""
    return {
        **mapping_or_empty(verification.get("environment")),
        **mapping_or_empty(verification.get("evidence")),
    }


def _blocker_lines(verification: JsonObject, facts: JsonObject) -> list[str]:
    """Every reason the core gave, verbatim with its remedy; the console classifies none of them."""
    lines: list[str] = []
    for item in items_or_empty(facts.get("blockers")):
        reason, remedy = (
            _text(mapping_or_empty(item).get("reason")),
            _text(mapping_or_empty(item).get("remedy")),
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
    if name in items_or_empty(verification.get("verified")):
        return State.OK
    if name in items_or_empty(verification.get("unverified")):
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
        facts.get("engine"),
        _text(mapping_or_empty(plan.get("container")).get("engine")),
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
            State.OK
            if transport == "external"
            else State.WARN
            if transport
            else State.NOT_REPORTED,
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
        mapping_or_empty(item)
        for item in items_or_empty(
            mapping_or_empty(verification.get("required")).get("filesystem")
        )
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
        str(item)
        for item in items_or_empty(
            mapping_or_empty(verification.get("required")).get("hosts")
        )
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
