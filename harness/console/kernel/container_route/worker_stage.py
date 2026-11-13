"""The Worker stage: the execution of the created dispatch as `dispatch status` reports it."""

from __future__ import annotations


from ..coordinator_api import ApiResult
from ..json_fields import items as _items
from ..json_fields import mapping as _obj
from .model import (
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
