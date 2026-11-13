"""The QA stage: the separate role=qa dispatch, its run in a container and the lane."""

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
)
from .plan_stage import Proposal
from .worker_stage import _mapping_text


@dataclass
class QaState:
    """The QA route's own documents: its proposal, its dispatch, its run and the lane."""

    proposal: Proposal | None = None
    proposal_result: ApiResult | None = None
    created: ApiResult | None = None
    run: ApiResult | None = None
    report: JsonObject | None = None
    status: ApiResult | None = None


_OUTCOME_STATES = {
    "completed": State.OK,
    "blocked": State.BLOCKED,
    "failed": State.FAILED,
}


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
                        _OUTCOME_STATES.get(
                            _text(qa.report.get("outcome")), State.NOT_REPORTED
                        ),
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
