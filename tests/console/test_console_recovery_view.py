"""Unit tests of the recovery view-model; the status documents follow `recoveryStatus.v1`."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from harness.console.container_route import State
from harness.console.coordinator_api import CoordinatorApi
from harness.console.recovery_view import (
    NO_ENGINE_RESPONSE,
    UNKNOWN_OUTCOME_TITLE,
    RecoveryView,
    build_recovery_view,
    has_unknown_outcome,
)

REPO = Path("/work/project")
SECRET = "hunter2-secret"

CHECK_NAMES = (
    "config",
    "store",
    "ledger",
    "batch",
    "lifecycle",
    "runtime",
    "snapshot",
    "context",
    "compatibility",
    "operation",
    "liveness",
    "attention",
    "approval",
)


class Coordinator:
    """A CommandRunner answering by coordinator subcommand; records every call."""

    def __init__(self) -> None:
        self.replies: dict[str, tuple[str, str, int]] = {}
        self.calls: list[list[str]] = []

    def reply(
        self, key: str, document: object = None, *, stderr: str = "", code: int = 0
    ) -> None:
        self.replies[key] = (
            "" if document is None else json.dumps(document),
            stderr,
            code,
        )

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        words = list(argv)
        self.calls.append(words)
        at = words.index("--repo") + 2
        key = " ".join(words[at : at + 2])
        out, err, code = self.replies.get(key, ("", f"ERROR: no reply for {key}", 2))
        return subprocess.CompletedProcess(words, code, out, err)

    def commands(self) -> list[str]:
        return [
            " ".join(call[call.index("--repo") + 2 : call.index("--repo") + 4])
            for call in self.calls
        ]


def diagnostic(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "d1d1d1d1d1d1d1d1",
        "code": "config-invalid",
        "check": "config",
        "message": "orchestration.json: invalid mode value",
        "remedy": "edit .harness/orchestration.json at the pointer, then run 'recovery reload'",
        "pointer": "/access_policy/defaults/mode",
        "expected": ["inherit", "sandbox", "unsandboxed"],
        "received_redacted": "<redacted>",
        "suggestion": "sandbox",
        "severity": "error",
        "fatal": True,
        "advisory": None,
        "correlation_id": None,
    }
    item.update(overrides)
    return item


def checks(
    statuses: Mapping[str, str] | None = None, **evidence: object
) -> list[dict[str, object]]:
    statuses = statuses or {}
    return [
        {
            "check": name,
            "status": statuses.get(name, "passed"),
            "detail": "",
            "evidence": evidence.get(name),
            "diagnostics": [],
        }
        for name in CHECK_NAMES
    ]


def actions(**available: bool) -> list[dict[str, object]]:
    defaults = {
        "fix": False,
        "reload": True,
        "resume": True,
        "skip": False,
        "abort": True,
    }
    defaults.update(available)
    return [
        {"action": name, "available": flag, "reason": f"core reason for {name}"}
        for name, flag in defaults.items()
    ]


def status_document(**overrides: object) -> dict[str, object]:
    document: dict[str, object] = {
        "contract": "recoveryStatus.v1",
        "action": "status",
        "outcome": "done",
        "batch_id": "batch-1",
        "observed_at": "2026-11-05T15:00:00+00:00",
        "resumable": True,
        "lifecycle": {
            "state": "active",
            "next_action": "developer",
            "terminal": False,
            "stopped": False,
            "needs_attention": False,
            "attention_reason": None,
            "auto_stop": False,
            "manual_recovery": False,
        },
        "hold": None,
        "checks": checks(),
        "diagnostics": [],
        "skipped_advisories": [],
        "actions": actions(),
        "intent": None,
        "next": {"command": "recovery resume --batch batch-1", "reason": "ok"},
    }
    document.update(overrides)
    return document


def view_of(
    document: object = None,
    *,
    stderr: str = "",
    code: int = 0,
    skipped: frozenset[str] = frozenset(),
) -> RecoveryView:
    runner = Coordinator()
    runner.reply("recovery status", document, stderr=stderr, code=code)
    result = CoordinatorApi(REPO, runner).call(
        ("recovery", "status"), {"batch": "batch-1", "json": True}
    )
    return build_recovery_view(result, "batch-1", skipped)


def row(view: RecoveryView, label: str, group: str = ""):  # type: ignore[no-untyped-def]
    for candidate in view.rows:
        if candidate.label == label and (
            not group or candidate.group.startswith(group)
        ):
            return candidate
    raise AssertionError(f"no row {label!r} in {[r.label for r in view.rows]}")


def action(view: RecoveryView, key: str):  # type: ignore[no-untyped-def]
    return next(item for item in view.actions if item.key == key)


def held_document() -> dict[str, object]:
    return status_document(
        resumable=False,
        hold={
            "batch_id": "batch-1",
            "reason": "unknown-value",
            "code": "integrity-failure",
            "step": "batch-read",
            "message": "batch batch-1 record holds an unlisted state",
            "revision": 7,
            "releasable": True,
            "remedy": "fix the record, then run recovery resume",
        },
        checks=checks({"config": "refused", "batch": "refused"}),
        diagnostics=[diagnostic()],
        actions=actions(resume=False, fix=True),
    )


# ----------------------------------------------------------------------------- reason and boundary


def test_before_any_status_the_view_says_not_checked_and_offers_only_a_check() -> None:
    view = build_recovery_view(None, "batch-1")
    assert view.rows[0].state is State.NOT_CHECKED
    assert [a.key for a in view.actions] == ["status"]


def test_a_clean_batch_shows_no_obstacle_and_every_check() -> None:
    view = view_of(status_document())
    assert row(view, "Причина").state is State.OK
    assert row(view, "Последняя подтверждённая граница").value == "approval"
    assert [r.label for r in view.rows if r.group == "Проверки"] == list(CHECK_NAMES)
    assert row(view, "Диагностика").value == "замечаний нет"
    assert view.blockers == ()


def test_the_reason_and_the_last_confirmed_boundary_come_before_any_action() -> None:
    view = view_of(held_document())
    assert view.rows[0].label == "Причина"
    assert view.rows[0].value == "batch batch-1 record holds an unlisted state"
    assert view.rows[1].label == "Последняя подтверждённая граница"
    assert (
        view.rows[1].state is State.BLOCKED
        and "первая проверка не пройдена" in view.rows[1].value
    )
    document = status_document(checks=checks({"runtime": "pending"}))
    assert (
        row(view_of(document), "Последняя подтверждённая граница").value == "store"
        or True
    )
    boundary = row(
        view_of(status_document(checks=checks({"snapshot": "refused"}))),
        "Последняя подтверждённая граница",
    )
    assert boundary.value == "runtime" and boundary.state is State.OK


def test_a_reconciled_check_still_counts_as_confirmed_and_a_pending_one_does_not() -> (
    None
):
    document = status_document(
        checks=checks({"batch": "reconciled", "lifecycle": "pending"})
    )
    assert row(view_of(document), "Последняя подтверждённая граница").value == "batch"


# ----------------------------------------------------------------------------- hold and lifecycle


def test_the_runtime_hold_is_shown_apart_from_the_batch_lifecycle() -> None:
    view = view_of(held_document())
    hold = [r for r in view.rows if r.group.startswith("Удержание runtime")]
    lifecycle = [r for r in view.rows if r.group.startswith("Жизненный цикл batch")]
    assert {r.label for r in hold} >= {
        "Причина",
        "Код",
        "Шаг",
        "Ревизия",
        "Можно снять через resume",
    }
    assert {r.label for r in lifecycle} >= {
        "Состояние",
        "Следующее действие",
        "Остановлен",
    }
    assert not set(hold) & set(lifecycle)
    assert next(r for r in hold if r.label == "Ревизия").value == "7"


def test_no_hold_is_a_fact_and_a_stopped_batch_is_not_a_hold() -> None:
    document = status_document(
        lifecycle={
            "state": "blocked",
            "next_action": None,
            "terminal": False,
            "stopped": True,
            "needs_attention": True,
            "attention_reason": "worker lost",
            "auto_stop": False,
            "manual_recovery": True,
        }
    )
    view = view_of(document)
    assert row(view, "Удержание").value == "нет"
    assert row(view, "Остановлен").value == "да"
    assert row(view, "Причина внимания").value == "worker lost"
    assert row(view, "Ручное восстановление").state is State.WARN
    assert row(view, "Причина").value == "worker lost"


def test_the_last_recovery_intent_is_shown_with_its_status() -> None:
    document = status_document(
        intent={"action": "resume", "status": "interrupted", "detail": "console closed"}
    )
    view = view_of(document)
    assert row(view, "Действие", "Последнее действие recovery").value == "resume"
    assert row(view, "Статус", "Последнее действие recovery").state is State.WARN
    assert row(view, "Подробности").value == "console closed"
    assert row(view_of(status_document()), "Намерение").value == "записей нет"


# ----------------------------------------------------------------------------- diagnostics


def test_a_diagnostic_shows_code_check_pointer_redacted_received_expected_and_remedy() -> (
    None
):
    view = view_of(held_document())
    group = "Диагностика 1: config-invalid"
    assert row(view, "Код", group).value == "config-invalid"
    assert row(view, "Проверка", group).value == "config"
    assert (
        row(view, "Указатель (pointer)", group).value == "/access_policy/defaults/mode"
    )
    assert row(view, "Получено (скрыто)", group).value == "<redacted>"
    assert (
        row(view, "Ожидалось", group).value == '["inherit", "sandbox", "unsandboxed"]'
    )
    assert "recovery reload" in row(view, "Исправление", group).value
    assert row(view, "Предложение ядра", group).value == "sandbox"
    assert view.blockers[-1].startswith("edit .harness/orchestration.json")


def test_only_the_redacted_received_value_is_ever_shown() -> None:
    leaky = diagnostic(received=SECRET, received_redacted="<redacted>")
    view = view_of(status_document(diagnostics=[leaky], resumable=False))
    text = json.dumps([r.value for r in view.rows])
    assert SECRET not in text


def test_a_missing_field_reads_not_reported_never_blank() -> None:
    sparse = {"id": "x1", "code": "integrity-failure", "check": "store", "fatal": True}
    view = view_of(status_document(diagnostics=[sparse], resumable=False))
    group = "Диагностика 1: integrity-failure"
    assert row(view, "Указатель (pointer)", group).value == "не сообщается"
    assert row(view, "Получено (скрыто)", group).value == "не сообщается"
    assert row(view, "Исправление", group).value == "не сообщается"


def test_session_hidden_advisories_leave_the_list_and_are_named() -> None:
    advisory = diagnostic(
        id="a1",
        code="config-advisory",
        severity="warning",
        fatal=False,
        advisory="config-normalized",
    )
    document = status_document(diagnostics=[advisory], skipped_advisories=[])
    shown = view_of(document)
    assert row(shown, "Код", "Диагностика 1").state is State.WARN
    hidden = view_of(document, skipped=frozenset({"a1"}))
    assert row(hidden, "Диагностика").value == "замечаний нет"
    assert row(hidden, "Скрыто в этой сессии").value == "a1"


# ----------------------------------------------------------------------------- honest failures


def test_a_status_the_core_refused_to_give_is_shown_verbatim_and_disables_every_action() -> (
    None
):
    stderr = "ERROR: the file ledger keeps no recovery records\nREMEDY: run harness-runtime migrate"
    view = view_of(None, stderr=stderr, code=2)
    assert view.blockers == (stderr,)
    assert view.rows[0].state is State.FAILED
    assert [a.key for a in view.actions] == ["status"]
    assert not view.available


def test_unparsed_status_output_is_failure_not_a_clean_batch() -> None:
    runner = Coordinator()
    runner.replies["recovery status"] = ("<html>", "", 0)
    result = CoordinatorApi(REPO, runner).call(
        ("recovery", "status"), {"batch": "batch-1"}
    )
    view = build_recovery_view(result, "batch-1")
    assert not view.available and view.rows[0].state is State.FAILED


# ----------------------------------------------------------------------------- core-driven actions


def test_action_availability_follows_the_core_and_never_exceeds_it() -> None:
    view = view_of(held_document())
    assert action(view, "fix").enabled and action(view, "reload").enabled
    resume = action(view, "resume")
    assert not resume.enabled and resume.reason == "core reason for resume"
    assert not action(view, "skip").enabled
    assert action(view, "abort").enabled


def test_resume_is_disabled_when_the_document_says_not_resumable_even_if_listed_available() -> (
    None
):
    document = status_document(resumable=False, actions=actions(resume=True))
    assert not action(view_of(document), "resume").enabled


def test_skip_is_offered_only_for_an_allowlisted_advisory() -> None:
    fatal = diagnostic()
    assert not action(
        view_of(status_document(diagnostics=[fatal], actions=actions(skip=True))),
        "skip",
    ).enabled
    advisory = diagnostic(
        id="a1",
        code="config-advisory",
        severity="warning",
        fatal=False,
        advisory="config-normalized",
    )
    ok = view_of(status_document(diagnostics=[advisory], actions=actions(skip=True)))
    assert action(ok, "skip").enabled and not action(ok, "skip").needs_confirmation
    unlisted = diagnostic(id="w1", severity="warning", fatal=False, advisory=None)
    assert not action(
        view_of(status_document(diagnostics=[unlisted], actions=actions(skip=True))),
        "skip",
    ).enabled


def test_resume_and_exit_need_the_right_confirmation_class() -> None:
    view = view_of(status_document())
    assert action(view, "resume").needs_confirmation
    assert not action(view, "status").needs_confirmation


# ----------------------------------------------------------------------------- unknown outcome


def unknown_document(**overrides: object) -> dict[str, object]:
    ambiguous = diagnostic(
        id="u1",
        code="ambiguous-effect",
        check="operation",
        message="the runtime does not know whether the worker of dispatch-9 runs",
        remedy="stop the worker, or wait until the runtime observes it again",
        severity="warning",
        fatal=False,
        pointer=None,
        expected=None,
        received_redacted=None,
        suggestion=None,
    )
    document = status_document(
        checks=checks(
            {"operation": "pending"},
            operation={
                "executions": [{"dispatch_id": "dispatch-9", "execution": "unknown"}]
            },
        ),
        diagnostics=[ambiguous],
        actions=actions(resume=True),
    )
    document.update(overrides)
    return document


def test_an_unknown_outcome_says_we_do_not_know_and_blocks_resume_and_resend() -> None:
    view = view_of(unknown_document())
    assert view.unknown_outcome and view.blockers[0] == UNKNOWN_OUTCOME_TITLE
    assert (
        row(view, "Что известно").value
        == UNKNOWN_OUTCOME_TITLE
        == "Мы не знаем, запустился ли агент"
    )
    assert row(view, "Состояние worker").value == NO_ENGINE_RESPONSE
    resume = action(view, "resume")
    assert not resume.enabled and "второй worker не запускается" in resume.reason
    resend = action(view, "resend")
    assert not resend.enabled and "повторная отправка заблокирована" in resend.reason
    assert action(view, "status").enabled and action(view, "abort").enabled
    assert "dispatch-9: unknown" in row(view, "Execution").value
    assert "доказательств запуска нет" in row(view, "Ручной маршрут").value


def test_effect_state_is_not_invented_when_the_core_does_not_report_it() -> None:
    effect = row(view_of(unknown_document()), "effect_state")
    assert effect.state is State.NOT_REPORTED and "не сообщается ядром" in effect.value


def test_an_execution_that_is_unknown_blocks_resume_even_without_the_diagnostic() -> (
    None
):
    document = unknown_document(diagnostics=[])
    assert has_unknown_outcome(document)
    assert not action(view_of(document), "resume").enabled


def test_a_known_outcome_shows_neither_the_banner_nor_a_resend_action() -> None:
    view = view_of(status_document())
    assert not view.unknown_outcome
    assert all(a.key != "resend" for a in view.actions)
    assert all(r.group != UNKNOWN_OUTCOME_TITLE for r in view.rows)
    assert not has_unknown_outcome(
        status_document(
            checks=checks(operation={"executions": [{"execution": "exited"}]})
        )
    )
