"""The Plan / approval stage: the held `dispatch propose` and its explicit approval."""

from __future__ import annotations

from dataclasses import dataclass

from ..coordinator_api import ApiResult
from ..json_fields import items as _items
from ..json_fields import mapping as _obj
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
from .preflight_stage import _packet, verification_status


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
