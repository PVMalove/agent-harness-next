"""View-model of the recovery screen over `recovery status --json` (`recoveryStatus.v1`). Textual-free.

What keeps a batch from going on, and what may be done about it, is decided by the core: the view
shows the reason and the last confirmed boundary before any action, the runtime hold apart from the
batch lifecycle, and every diagnostic with its code, check, pointer, redacted received value,
expected value and remedy. Action availability comes from the core's own `actions` list; the only
change the view makes is to withhold more: an execution the runtime cannot account for blocks Resume
and any resend, whatever the core's `actions` say. Only `received_redacted` is ever shown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping

from .container_route import (
    Action,
    Effect,
    JsonObject,
    Row,
    State,
    _items,
    _obj,
    _text,
    _call_failure,
)
from .coordinator_api import ApiResult

CHECK_STATES = {
    "passed": State.OK,
    "reconciled": State.INFO,
    "pending": State.WARN,
    "refused": State.BLOCKED,
    "skipped": State.NOT_CHECKED,
}
# A check whose status a later `resume` settles by itself; the boundary stops before the first
# check that is not passed or reconciled.
CONFIRMED = frozenset({"passed", "reconciled"})

UNKNOWN_OUTCOME_TITLE = "Мы не знаем, запустился ли агент"
NO_ENGINE_RESPONSE = "нет ответа движка"


def _value_text(value: object) -> str:
    """A core value as text; a structure becomes stable JSON so it stays one readable block."""
    if value is None:
        return "не сообщается"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class DiagnosticView:
    """One finding, shown field by field. `received` never appears: the core's redacted copy does."""

    id: str
    code: str
    check: str
    message: str
    pointer: str
    expected: object
    received_redacted: object
    suggestion: object
    remedy: str
    fatal: bool
    advisory: str | None

    @classmethod
    def of(cls, item: Mapping[str, object]) -> "DiagnosticView":
        return cls(
            id=_text(item.get("id")),
            code=_text(item.get("code"), "—"),
            check=_text(item.get("check"), "—"),
            message=_text(item.get("message")),
            pointer=_text(item.get("pointer")),
            expected=item.get("expected"),
            received_redacted=item.get("received_redacted"),
            suggestion=item.get("suggestion"),
            remedy=_text(item.get("remedy")),
            fatal=item.get("fatal") is not False,
            advisory=_text(item.get("advisory")) or None,
        )

    @property
    def skippable(self) -> bool:
        """An allowlisted advisory only; the core refuses anything else, and so does the view."""
        return not self.fatal and self.advisory is not None

    def rows(self, index: int) -> list[Row]:
        group = f"Диагностика {index}: {self.code}"
        rows = [
            Row("Код", self.code, State.BLOCKED if self.fatal else State.WARN, group),
            Row("Проверка", self.check, None, group),
            Row("Указатель (pointer)", self.pointer or "не сообщается", None, group),
            Row("Сообщение", self.message or "не сообщается", None, group),
            Row("Получено (скрыто)", _value_text(self.received_redacted), None, group),
            Row("Ожидалось", _value_text(self.expected), None, group),
            Row("Исправление", self.remedy or "не сообщается", None, group),
        ]
        if self.suggestion is not None:
            rows.append(
                Row("Предложение ядра", _value_text(self.suggestion), State.INFO, group)
            )
        if self.advisory:
            rows.append(Row("Advisory", self.advisory, State.INFO, group))
        return rows


@dataclass(frozen=True)
class RecoveryView:
    """Everything the recovery screen draws, read once from a status document."""

    batch: str
    result: ApiResult | None
    document: JsonObject
    diagnostics: tuple[DiagnosticView, ...] = ()
    skipped: frozenset[str] = frozenset()
    unknown_outcome: bool = False
    rows: tuple[Row, ...] = ()
    blockers: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    actions: tuple[Action, ...] = field(default_factory=tuple)

    @property
    def available(self) -> bool:
        return bool(self.document)


def has_unknown_outcome(document: Mapping[str, object]) -> bool:
    """True when the runtime cannot say whether a worker runs: the core's `ambiguous-effect`
    diagnostic, or an observed execution whose state is `unknown`."""
    if any(
        _obj(item).get("code") == "ambiguous-effect"
        for item in _items(document.get("diagnostics"))
    ):
        return True
    for check in _items(document.get("checks")):
        entry = _obj(check)
        if entry.get("check") != "operation":
            continue
        for run in _items(_obj(entry.get("evidence")).get("executions")):
            if _obj(run).get("execution") == "unknown":
                return True
    return False


def _boundary(document: Mapping[str, object]) -> tuple[str, State]:
    """The last check the core confirmed before the first one it did not."""
    last = ""
    for check in _items(document.get("checks")):
        entry = _obj(check)
        if _text(entry.get("status")) not in CONFIRMED:
            break
        last = _text(entry.get("check"))
    if last:
        return last, State.OK
    return "нет подтверждённой границы: первая проверка не пройдена", State.BLOCKED


def _reason(document: Mapping[str, object]) -> tuple[str, State]:
    hold = _obj(document.get("hold"))
    if hold:
        return _text(
            hold.get("message"), _text(hold.get("reason"), "не сообщается")
        ), State.BLOCKED
    for item in _items(document.get("diagnostics")):
        data = _obj(item)
        if data.get("fatal") is not False:
            return _text(data.get("message"), "не сообщается"), State.BLOCKED
    lifecycle = _obj(document.get("lifecycle"))
    if lifecycle.get("attention_reason"):
        return _text(lifecycle["attention_reason"]), State.WARN
    if document.get("resumable") is True:
        return "препятствий нет: проверки пройдены или согласуются resume", State.OK
    return "причина не сообщается", State.NOT_REPORTED


def _intent_rows(intent: JsonObject) -> list[Row]:
    group = "Последнее действие recovery"
    if not intent:
        return [Row("Намерение", "записей нет", State.INFO, group)]
    rows = [Row("Действие", _text(intent.get("action"), "не сообщается"), None, group)]
    status = _text(intent.get("status"), "не сообщается")
    state = {
        "done": State.OK,
        "refused": State.BLOCKED,
        "interrupted": State.WARN,
        "pending": State.PENDING,
    }.get(status, State.INFO)
    rows.append(Row("Статус", status, state, group))
    if intent.get("detail"):
        rows.append(Row("Подробности", _text(intent["detail"]), None, group))
    return rows


def _hold_rows(hold: JsonObject) -> list[Row]:
    group = "Удержание runtime (не жизненный цикл batch)"
    if not hold:
        return [Row("Удержание", "нет", State.OK, group)]
    return [
        Row(
            "Причина", _text(hold.get("reason"), "не сообщается"), State.BLOCKED, group
        ),
        Row("Код", _text(hold.get("code"), "не сообщается"), None, group),
        Row("Шаг", _text(hold.get("step"), "не сообщается"), None, group),
        Row("Сообщение", _text(hold.get("message"), "не сообщается"), None, group),
        Row("Ревизия", _text(hold.get("revision"), "не сообщается"), None, group),
        Row(
            "Можно снять через resume",
            "да" if hold.get("releasable") else "нет",
            State.INFO,
            group,
        ),
        Row("Исправление", _text(hold.get("remedy"), "не сообщается"), None, group),
    ]


def _lifecycle_rows(lifecycle: JsonObject) -> list[Row]:
    group = "Жизненный цикл batch (запись ядра, recovery её не меняет)"
    if not lifecycle:
        return [Row("Жизненный цикл", "не сообщается", State.NOT_REPORTED, group)]
    rows = [
        Row("Состояние", _text(lifecycle.get("state"), "не сообщается"), None, group),
        Row(
            "Следующее действие",
            _text(lifecycle.get("next_action"), "не сообщается"),
            None,
            group,
        ),
        Row("Терминальный", "да" if lifecycle.get("terminal") else "нет", None, group),
        Row("Остановлен", "да" if lifecycle.get("stopped") else "нет", None, group),
        Row(
            "Требует внимания",
            "да" if lifecycle.get("needs_attention") else "нет",
            State.WARN if lifecycle.get("needs_attention") else None,
            group,
        ),
    ]
    if lifecycle.get("attention_reason"):
        rows.append(
            Row("Причина внимания", _text(lifecycle["attention_reason"]), None, group)
        )
    if lifecycle.get("manual_recovery"):
        rows.append(Row("Ручное восстановление", "требуется", State.WARN, group))
    return rows


def _unknown_rows(document: Mapping[str, object]) -> list[Row]:
    group = UNKNOWN_OUTCOME_TITLE
    rows = [
        Row("Что известно", UNKNOWN_OUTCOME_TITLE, State.UNKNOWN, group),
        Row(
            "effect_state",
            "не сообщается ядром: контракт recoveryStatus.v1 его не содержит",
            State.NOT_REPORTED,
            group,
        ),
        Row("Состояние worker", NO_ENGINE_RESPONSE, State.UNKNOWN, group),
    ]
    for check in _items(document.get("checks")):
        entry = _obj(check)
        if entry.get("check") != "operation":
            continue
        for run in _items(_obj(entry.get("evidence")).get("executions")):
            item = _obj(run)
            rows.append(
                Row(
                    "Execution",
                    f"{_text(item.get('dispatch_id'), '—')}: {_text(item.get('execution'), 'не сообщается')}",
                    State.UNKNOWN if item.get("execution") == "unknown" else None,
                    group,
                )
            )
    rows.append(
        Row(
            "Ручной маршрут",
            "доказательств запуска нет: остановите worker вручную или дождитесь повторного "
            "наблюдения runtime; повторная отправка и resume заблокированы",
            State.BLOCKED,
            group,
        )
    )
    return rows


def _core_actions(document: Mapping[str, object]) -> dict[str, tuple[bool, str]]:
    return {
        _text(_obj(item).get("action")): (
            _obj(item).get("available") is True,
            _text(_obj(item).get("reason")),
        )
        for item in _items(document.get("actions"))
    }


UNKNOWN_BLOCK = (
    "исход запуска неизвестен: доказательств нет, второй worker не запускается"
)
RESEND_BLOCK = "повторная отправка заблокирована: сначала нужно доказательство, что worker не запущен"


def _actions(
    document: Mapping[str, object],
    diagnostics: tuple[DiagnosticView, ...],
    unknown: bool,
) -> tuple[Action, ...]:
    """Check state, then the core's own five actions. The core decides availability; the view only
    withholds more (an unknown outcome) and never enables what the core refused."""
    core = _core_actions(document)

    def pick(key: str, label: str, effect: Effect, extra: str = "") -> Action:
        available, reason = core.get(key, (False, "ядро не сообщает это действие"))
        if available and extra:
            return Action(key, label, False, extra, effect)
        return Action(key, label, available, reason, effect)

    skippable = any(item.skippable for item in diagnostics)
    skip_available, skip_reason = core.get(
        "skip", (False, "ядро не сообщает это действие")
    )
    resume_ok = document.get("resumable") is True
    resume = pick("resume", "Resume", Effect.RUN, UNKNOWN_BLOCK if unknown else "")
    if resume.enabled and not resume_ok:
        resume = Action(
            "resume", "Resume", False, "ядро: проверка не пройдена", Effect.RUN
        )
    actions = [
        Action("status", "Проверить состояние", True, "", Effect.OBSERVE),
        pick("fix", "Fix", Effect.RECORD),
        pick("reload", "Reload", Effect.RECORD),
        resume,
        Action(
            "skip",
            "Скрыть advisory",
            skip_available and skippable,
            skip_reason if not (skip_available and skippable) else "",
            Effect.READ,
        ),
        pick("abort", "Выйти с сохранением", Effect.RECORD),
    ]
    if unknown:
        actions.append(
            Action(
                "resend", "Повторная отправка worker", False, RESEND_BLOCK, Effect.RUN
            )
        )
    return tuple(actions)


def build_recovery_view(
    result: ApiResult | None,
    batch: str,
    skipped: frozenset[str] = frozenset(),
) -> RecoveryView:
    """The screen's whole view from one `recovery status` answer (or none yet)."""
    refresh = Action("status", "Проверить состояние", True, "", Effect.OBSERVE)
    if result is None:
        pending = (
            Row(
                "Состояние",
                "не проверено: статус ещё не запрашивался",
                State.NOT_CHECKED,
            ),
        )
        return RecoveryView(batch, None, {}, rows=pending, actions=(refresh,))
    if not result.ok or result.document is None:
        failure = _call_failure("Статус recovery", result)
        reason = result.problem_text or result.outcome.value
        return RecoveryView(
            batch,
            result,
            {},
            rows=(failure,),
            blockers=(reason,),
            actions=(refresh,),
            notes=(
                "Состояние recovery не получено: действия недоступны, пока ядро не ответит.",
            ),
        )
    document = result.document
    diagnostics = tuple(
        DiagnosticView.of(_obj(item))
        for item in _items(document.get("diagnostics"))
        if _text(_obj(item).get("id")) not in skipped
    )
    unknown = has_unknown_outcome(document)
    reason, reason_state = _reason(document)
    boundary, boundary_state = _boundary(document)
    rows: list[Row] = [
        Row("Причина", reason, reason_state, "Причина и граница"),
        Row(
            "Последняя подтверждённая граница",
            boundary,
            boundary_state,
            "Причина и граница",
        ),
        Row(
            "Можно продолжить",
            "да, по проверкам ядра" if document.get("resumable") is True else "нет",
            State.OK if document.get("resumable") is True else State.BLOCKED,
            "Причина и граница",
        ),
    ]
    rows.extend(_hold_rows(_obj(document.get("hold"))))
    rows.extend(_lifecycle_rows(_obj(document.get("lifecycle"))))
    rows.extend(_intent_rows(_obj(document.get("intent"))))
    if unknown:
        rows.extend(_unknown_rows(document))
    for check in _items(document.get("checks")):
        entry = _obj(check)
        status = _text(entry.get("status"), "—")
        text = status + (
            f": {_text(entry.get('detail'))}" if entry.get("detail") else ""
        )
        rows.append(
            Row(
                _text(entry.get("check"), "—"),
                text,
                CHECK_STATES.get(status, State.NOT_REPORTED),
                "Проверки",
            )
        )
    for index, diagnostic in enumerate(diagnostics, start=1):
        rows.extend(diagnostic.rows(index))
    if not diagnostics:
        rows.append(Row("Диагностика", "замечаний нет", State.OK, "Диагностика"))
    hidden = [str(item) for item in _items(document.get("skipped_advisories"))]
    if hidden or skipped:
        rows.append(
            Row(
                "Скрыто в этой сессии",
                ", ".join(sorted({*hidden, *skipped})),
                State.INFO,
                "Диагностика",
            )
        )
    blockers = [
        d.remedy or d.message
        for d in diagnostics
        if d.fatal and (d.remedy or d.message)
    ]
    if unknown:
        blockers.insert(0, UNKNOWN_OUTCOME_TITLE)
    notes = (
        "Resume, Fix и Reload — отдельные действия ядра; выход с сохранением не отменяет batch и "
        "не останавливает worker.",
    )
    return RecoveryView(
        batch,
        result,
        document,
        diagnostics,
        skipped,
        unknown,
        tuple(rows),
        tuple(blockers),
        notes,
        _actions(document, diagnostics, unknown),
    )
