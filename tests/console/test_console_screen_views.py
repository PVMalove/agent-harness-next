"""The Recovery and Container route view payloads are the serialised objects of the kernel
view-models the TUI draws with; the served view never calls the coordinator."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from harness.console.kernel.batch_history import (
    BatchHistorySource,
    History,
    HistoryBatch,
    recovery_entry_from,
)
from harness.console.kernel.container_route import (
    Authored,
    RouteSession,
    Stage,
    mark,
)
from harness.console.kernel.coordinator_api import ApiResult, Outcome
from harness.console.kernel.recovery_view import RecoverySession, build_recovery_view
from harness.console.kernel.screen_views import (
    action_payload,
    recovery_view_payload,
    route_view_payload,
    row_payload,
    stage_view_payload,
)

from .test_console_container_route import (
    AUTHORED_DOCUMENT,
    preflight_document,
    verification,
)
from .test_console_recovery_view import actions, diagnostic, status_document

HISTORY = History(
    (
        HistoryBatch("batch-1", "#711", "br", "active", "t1", False, 2, 1, "developer"),
        HistoryBatch("batch-0", "#710", "br0", "completed", "t0", True, 1, 0, ""),
    )
)


def _result(
    outcome: Outcome, document: dict[str, object] | None, stderr: str = ""
) -> ApiResult:
    documents = (document,) if document is not None else ()
    return ApiResult(outcome, ("recovery", "status"), documents, 0, stderr)


class Raising:
    """A client the served views must never call."""

    calls = 0

    def call(self, *args: object, **kwargs: object) -> ApiResult:
        Raising.calls += 1
        raise AssertionError("the served view called the coordinator")

    def cleanup(self, *, apply_digest: str | None = None) -> ApiResult:
        return self.call()


def _expected_recovery(
    status: ApiResult | None, skip: tuple[str, ...]
) -> tuple[dict[str, object], dict[str, object]]:
    session = RecoverySession(Path("."), "batch-1", api=Raising())
    session.status = status
    session.skipped = set(skip)
    view = session.view()
    plan = session.resume_plan()
    return {
        "batch": "batch-1",
        "unknown_outcome": view.unknown_outcome,
        "rows": [row_payload(row) for row in view.rows],
        "blockers": list(view.blockers),
        "notes": list(view.notes),
        "actions": [action_payload(action) for action in view.actions],
    }, {
        "command": plan.command,
        "checks": [list(item) for item in plan.checks],
        "approval_required": plan.approval_required,
        "next_step": plan.next_step,
    }


HOLD = status_document(
    hold={"reason": "runtime", "message": "runtime удерживает batch"},
    resumable=False,
    lifecycle={"state": "active", "stopped": True},
    diagnostics=[diagnostic(), diagnostic(id="a1", fatal=False, advisory="stale")],
    actions=actions(skip=True, fix=True),
)
UNKNOWN = status_document(
    intent={"action": "dispatch", "status": "interrupted"},
    diagnostics=[diagnostic(code="unknown-execution-outcome")],
)


@pytest.mark.parametrize(
    "status",
    [
        _result(Outcome.DOCUMENT, HOLD),
        _result(Outcome.DOCUMENT, UNKNOWN),
        _result(Outcome.REFUSED, status_document(resumable=False)),
        _result(Outcome.UNAVAILABLE, None, "coordinator недоступен"),
        _result(Outcome.DOCUMENT, status_document()),
    ],
)
def test_the_recovery_payload_serialises_the_session_view_and_plan(
    status: ApiResult,
) -> None:
    Raising.calls = 0
    payload = recovery_view_payload(HISTORY, status, "batch-1", ("a1",))
    view, plan = _expected_recovery(status, ("a1",))
    entry = recovery_entry_from("batch-1", status)
    assert payload == {
        "history": [
            {"batch_id": "batch-1", "label": HISTORY.batches[0].label},
            {"batch_id": "batch-0", "label": HISTORY.batches[1].label},
        ],
        "history_unavailable": "",
        "entry": {
            "batch_id": "batch-1",
            "enabled": entry.enabled,
            "state": entry.state.value,
            "mark": mark(entry.state),
            "reason": entry.reason,
        },
        "view": view,
        "resume_plan": plan,
    }
    assert Raising.calls == 0
    built = build_recovery_view(status, "batch-1", frozenset({"a1"}))
    served = payload["view"]
    assert isinstance(served, dict)
    assert served["rows"] == [row_payload(row) for row in built.rows]


def test_the_stopped_batch_needs_an_approval_in_the_resume_plan() -> None:
    payload = recovery_view_payload(
        HISTORY, _result(Outcome.DOCUMENT, HOLD), "batch-1", ()
    )
    plan = payload["resume_plan"]
    assert isinstance(plan, dict) and plan["approval_required"] is True
    entry = payload["entry"]
    assert isinstance(entry, dict) and entry["enabled"] is True
    assert entry["reason"] == "runtime удерживает batch"


def test_without_a_batch_only_the_history_and_its_problem_are_served() -> None:
    payload = recovery_view_payload(
        History(unavailable="batch list упал"), None, "", ()
    )
    assert payload == {
        "history": [],
        "history_unavailable": "batch list упал",
        "entry": None,
        "view": None,
        "resume_plan": None,
    }


def test_the_module_entry_gate_is_the_one_the_history_source_uses() -> None:
    result = _result(Outcome.FAILED, None, "boom")
    assert BatchHistorySource._entry_from("b", result) == recovery_entry_from(
        "b", result
    )


@pytest.mark.parametrize(
    "preflight",
    [
        None,
        ApiResult(
            Outcome.DOCUMENT, ("dispatch", "preflight"), (preflight_document(),), 0
        ),
        ApiResult(
            Outcome.REFUSED,
            ("dispatch", "preflight"),
            (preflight_document(verified=verification("unverified")),),
            2,
        ),
        ApiResult(Outcome.UNAVAILABLE, ("dispatch", "preflight"), (), None, "нет ядра"),
    ],
)
def test_the_route_payload_serialises_the_session_tabs_context_and_views(
    preflight: ApiResult | None,
) -> None:
    authored = Authored(AUTHORED_DOCUMENT)
    batch = "batch-1" if preflight is not None else ""
    payload = route_view_payload(authored, preflight, batch, "developer", "")
    session = RouteSession(Path("."), api=Raising(), load_authored=lambda _: authored)
    session.select(batch, "developer", "")
    session.preflight = preflight
    assert payload["selection"] == {"batch": batch, "role": "developer", "runtime": ""}
    assert payload["context"] == [list(item) for item in session.executor_context()]
    assert payload["tabs"] == [
        {
            "stage": tab.stage.value,
            "title": tab.title,
            "state": tab.state.value,
            "mark": mark(tab.state),
            "reason": tab.reason,
        }
        for tab in session.tabs()
    ]
    assert payload["stages"] == {
        stage.value: stage_view_payload(session.view(stage)) for stage in Stage
    }
    assert list(payload["stages"]) == [
        "setup",
        "preflight",
        "plan",
        "worker",
        "qa",
        "cleanup",
    ]


def test_a_row_without_a_state_has_no_mark_and_an_action_names_its_confirmation() -> (
    None
):
    view = build_recovery_view(None, "batch-1")
    first = replace(view.rows[0], state=None)
    assert row_payload(first)["mark"] == "" and row_payload(first)["state"] is None
    assert action_payload(view.actions[0]) == {
        "key": "status",
        "label": "Проверить состояние",
        "enabled": True,
        "reason": "",
        "effect": "observe",
        "needs_confirmation": False,
    }
