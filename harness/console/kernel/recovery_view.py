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
import shlex
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

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
from .coordinator_api import ApiResult, CoordinatorApi, CoordinatorCalls
from .runner import CommandRunner, capturing_runner

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


# ----------------------------------------------------------------------------- actions


class FixChoice(str, Enum):
    """Fix never picks for the operator: the core's normalization or an edit at the pointer."""

    NORMALIZE = "normalize"
    EDIT_AT_POINTER = "edit"


@dataclass(frozen=True)
class WizardTarget:
    """Where the existing configuration wizard opens for an explicit value choice; the core's
    suggestion is a proposal the operator may take, never applied here."""

    file: str
    path: tuple[str, ...]
    suggestion: object


@dataclass(frozen=True)
class FixPreview:
    """The core's preview of the normalization; `diff` is what a confirmed write would change."""

    diff: str
    result: ApiResult

    @property
    def writable(self) -> bool:
        return bool(self.diff.strip())


@dataclass(frozen=True)
class ResumePlan:
    """What `recovery resume` will do, as far as the core says before running it: the exact
    command, the checks it reconciles and whether a human approval is part of it."""

    command: str
    checks: tuple[tuple[str, str], ...]
    approval_required: bool
    next_step: str


def pointer_parts(pointer: str) -> tuple[str, ...]:
    """The inverse of `harness.diagnostics.pointer`: `/a/b~1c` is `("a", "b/c")`."""
    return tuple(
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer.split("/")[1:]
        if part
    )


def _approval_present(values: Mapping[str, str]) -> bool:
    return all(
        values.get(key, "").strip() for key in ("approved_by", "approved_at", "note")
    )


class RecoverySession:
    """One batch's recovery: the last status, the ids hidden for this session only and the last
    action's answer. Every call goes through the structured client; nothing decides what the core
    did not, and no method abandons a batch, stops a worker or starts one."""

    def __init__(
        self,
        repo: Path,
        batch: str,
        runner: CommandRunner = capturing_runner,
        *,
        api: CoordinatorCalls | None = None,
        now: Callable[[], str] = lambda: datetime.now(UTC).isoformat(
            timespec="seconds"
        ),
    ) -> None:
        self.repo = repo
        self.batch = batch
        self.api: CoordinatorCalls = api or CoordinatorApi(repo, runner)
        self._now = now
        self.status: ApiResult | None = None
        self.skipped: set[str] = set()  # this session only; never persisted
        self.preview: FixPreview | None = None
        self.last: tuple[str, ApiResult] | None = None

    # -- reading -------------------------------------------------------------------------
    def view(self) -> RecoveryView:
        base = build_recovery_view(self.status, self.batch, frozenset(self.skipped))
        if self.last is None:
            return base
        name, result = self.last
        extra = _action_rows(name, result, self.preview)
        blockers = list(base.blockers)
        if not result.ok and result.problem_text:
            blockers.append(result.problem_text)
        return replace(base, rows=(*base.rows, *extra), blockers=tuple(blockers))

    def _status_values(self) -> dict[str, str | list[str] | bool]:
        values: dict[str, str | list[str] | bool] = {"batch": self.batch, "json": True}
        if self.skipped:
            values["skip"] = sorted(self.skipped)
        return values

    def refresh(self) -> ApiResult:
        """`recovery status --json`: read-only; the core takes no lock and writes nothing."""
        self.status = self.api.call(("recovery", "status"), self._status_values())
        return self.status

    # -- actions -------------------------------------------------------------------------
    def _allowed(self, key: str) -> None:
        action = next((item for item in self.view().actions if item.key == key), None)
        if action is None or not action.enabled:
            raise PermissionError(action.reason if action else f"{key} is not offered")

    def reload(self) -> ApiResult:
        """`recovery reload`: re-reads and re-validates only; it never fixes, resumes or starts."""
        self._allowed("reload")
        result = self.api.call(
            ("recovery", "reload"), {"batch": self.batch, "json": True}
        )
        self.last = ("reload", result)
        return result

    def fix(
        self, choice: FixChoice | None, diagnostic_id: str = ""
    ) -> FixPreview | WizardTarget:
        """The explicit value choice. NORMALIZE previews the core's normalization (nothing is
        written); EDIT_AT_POINTER names where the wizard opens, with the core's suggestion."""
        if choice is None:
            raise ValueError("fix needs an explicit choice")
        if choice is FixChoice.EDIT_AT_POINTER:
            found = next(
                (
                    d
                    for d in self.view().diagnostics
                    if d.id == diagnostic_id and d.pointer
                ),
                None,
            )
            if found is None:
                raise ValueError("no diagnostic with a pointer to edit")
            return WizardTarget(
                "orchestration.json", pointer_parts(found.pointer), found.suggestion
            )
        self._allowed("fix")
        result = self.api.call(("recovery", "fix"), {"batch": self.batch, "json": True})
        diff = _text(_obj(result.document).get("diff")) if result.ok else ""
        self.preview = FixPreview(diff, result)
        self.last = ("fix", result)
        return self.preview

    def apply_fix(self, confirmed: bool) -> ApiResult:
        """`recovery fix --apply`, only after a preview that has a diff and only on an explicit
        confirmation. The core's configuration transaction still checks that nothing changed."""
        preview = self.preview
        if preview is None or not preview.writable:
            raise PermissionError("preview the diff before writing")
        if not confirmed:
            raise PermissionError("the write needs an explicit confirmation")
        result = self.api.call(
            ("recovery", "fix"),
            {"batch": self.batch, "json": True, "apply": True},
            confirmed=True,
        )
        self.preview = None  # a spent preview is never applied twice
        self.last = ("fix-apply", result)
        return result

    def skip(self, diagnostic_id: str) -> None:
        """Hide one allowlisted advisory for this session; the core re-checks it on every status."""
        found = next(
            (d for d in self.view().diagnostics if d.id == diagnostic_id), None
        )
        if found is None or not found.skippable:
            raise PermissionError("only an allowlisted advisory can be hidden")
        self.skipped.add(found.id)

    def resume_plan(self) -> ResumePlan:
        """The exact command and what it reconciles, shown before the confirmation."""
        document = self.view().document
        lifecycle = _obj(document.get("lifecycle"))
        stopped = lifecycle.get("stopped") is True
        argv = ["recovery", "resume", "--batch", self.batch, "--json"]
        if stopped:
            argv += [
                "--approved-by",
                "<имя>",
                "--approved-at",
                "<время>",
                "--note",
                "<заметка>",
            ]
        steps = tuple(
            (_text(_obj(item).get("check")), _text(_obj(item).get("status")))
            for item in _items(document.get("checks"))
        )
        following = _obj(document.get("next"))
        return ResumePlan(
            "coordinator.py " + shlex.join(argv),
            steps,
            stopped,
            _text(following.get("command") or following.get("reason"), "не сообщается"),
        )

    def resume(
        self, approved_by: str = "", note: str = "", *, confirmed: bool = False
    ) -> ApiResult:
        """`recovery resume`, enabled only by the core's answer and never past an unknown
        outcome. A stopped batch needs the human approval, all three values together;
        `confirmed` is the operator's confirmation the console server demands."""
        self._allowed("resume")
        plan = self.resume_plan()
        values: dict[str, str | list[str] | bool] = {"batch": self.batch, "json": True}
        if plan.approval_required:
            approval = {
                "approved_by": approved_by.strip(),
                "approved_at": self._now(),
                "note": note.strip(),
            }
            if not _approval_present(approval):
                raise ValueError("a stopped batch needs approved_by and a note")
            values.update(approval)
        result = self.api.call(("recovery", "resume"), values, confirmed=confirmed)
        self.last = ("resume", result)
        return result

    def abort(self) -> ApiResult:
        """`recovery abort`: leave recovery with everything saved. It abandons no batch, stops no
        worker and cleans no worktree, and the view shows the core's own flags to prove it."""
        self._allowed("abort")
        result = self.api.call(
            ("recovery", "abort"), {"batch": self.batch, "json": True}, confirmed=True
        )
        self.last = ("abort", result)
        return result


_FLAGS = (
    ("abandoned", "batch отменён"),
    ("worker_stopped", "worker остановлен"),
    ("worktree_cleaned", "worktree очищен"),
    ("worker_started", "worker запущен"),
    ("dispatch_created", "dispatch создан"),
)


def _action_rows(name: str, result: ApiResult, preview: FixPreview | None) -> list[Row]:
    group = f"Результат: {name}"
    if not result.documents:
        return [_call_failure(f"Результат {name}", result)]
    document = _obj(result.document)
    outcome = _text(document.get("outcome"), "не сообщается")
    rows = [
        Row(
            "Исход",
            outcome,
            State.OK
            if outcome == "done"
            else State.BLOCKED
            if outcome == "refused"
            else State.NOT_REPORTED,
            group,
        )
    ]
    for key, label in _FLAGS:
        if key in document:
            rows.append(Row(label, "да" if document[key] else "нет", State.INFO, group))
    if name in ("fix", "fix-apply"):
        diff = _text(document.get("diff"))
        rows.append(
            Row(
                "Diff (превью)",
                diff or "нечего нормализовать",
                State.INFO if diff else State.NOT_REPORTED,
                group,
            )
        )
        if "applied" in document:
            rows.append(
                Row(
                    "Записано",
                    "да" if document["applied"] else "нет",
                    State.OK if document["applied"] else State.INFO,
                    group,
                )
            )
        if document.get("backup_version"):
            rows.append(
                Row("Резервная копия", _text(document["backup_version"]), None, group)
            )
    if name == "reload":
        runtime = _obj(document.get("runtime"))
        if runtime:
            problems = [str(item) for item in _items(runtime.get("problems"))]
            rows.append(
                Row(
                    "Совместимость runtime",
                    "да"
                    if runtime.get("compatible")
                    else "нет: " + "; ".join(problems),
                    State.OK if runtime.get("compatible") else State.BLOCKED,
                    group,
                )
            )
    if name == "resume":
        for step in _items(document.get("steps")):
            data = _obj(step)
            rows.append(
                Row(
                    "Шаг",
                    f"{_text(data.get('step'))}: {_text(data.get('detail'))}",
                    None,
                    group,
                )
            )
        for refusal in _items(document.get("refusals")):
            data = _obj(refusal)
            rows.append(
                Row(
                    "Отказ",
                    _text(data.get("remedy")) or _text(data.get("message")),
                    State.BLOCKED,
                    group,
                )
            )
    for index, item in enumerate(_items(document.get("diagnostics")), start=1):
        rows.extend(DiagnosticView.of(_obj(item)).rows(index))
    return rows
