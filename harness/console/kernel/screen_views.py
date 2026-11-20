"""The Recovery and Container route views as JSON-safe payloads for the Web console. Textual-free,
standard library only.

The TUI draws these screens from the view-models of `recovery_view` and `container_route`; the
Web console reads the very same objects through the server, serialised here. Nothing is decided
in this module: every row, action, blocker and tab state is what the kernel functions returned,
so the Web console never holds a second copy of the recovery or container route rules.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from .batch_history import History, recovery_entry_from
from .container_route import (
    Action,
    Authored,
    RouteSession,
    Row,
    Stage,
    StageView,
    State,
    mark,
)
from .coordinator_api import ApiResult
from .recovery_view import RecoverySession

_NO_CALLS = "a served view never calls the coordinator"


class _NoCalls:
    """The client of a served view: the result is already known, so any call is a bug."""

    def call(
        self,
        path: tuple[str, ...],
        values: Mapping[str, str | Sequence[str] | bool] | None = None,
        *,
        confirmed: bool = False,
    ) -> ApiResult:
        raise RuntimeError(_NO_CALLS)

    def cleanup(self, *, apply_digest: str | None = None) -> ApiResult:
        raise RuntimeError(_NO_CALLS)


def _mark(state: State | None) -> str:
    return mark(state) if state is not None else ""


def row_payload(row: Row) -> dict[str, object]:
    """`{label, value, state, mark, group}`; `state` is null for a row without a status."""
    return {
        "label": row.label,
        "value": row.value,
        "state": row.state.value if row.state is not None else None,
        "mark": _mark(row.state),
        "group": row.group,
    }


def action_payload(action: Action) -> dict[str, object]:
    return {
        "key": action.key,
        "label": action.label,
        "enabled": action.enabled,
        "reason": action.reason,
        "effect": action.effect.value,
        "needs_confirmation": action.needs_confirmation,
    }


def stage_view_payload(view: StageView) -> dict[str, object]:
    return {
        "stage": view.stage.value,
        "rows": [row_payload(row) for row in view.rows],
        "actions": [action_payload(action) for action in view.actions],
        "blockers": list(view.blockers),
        "notes": list(view.notes),
    }


def recovery_view_payload(
    history: History, status: ApiResult | None, batch: str, skip: Sequence[str]
) -> dict[str, object]:
    """The batch history with its labels, the recovery gate of the selected batch, its recovery
    view and the resume plan, exactly as the TUI Recovery screen builds them."""
    entry: dict[str, object] | None = None
    view: dict[str, object] | None = None
    plan: dict[str, object] | None = None
    if batch and status is not None:
        found = recovery_entry_from(batch, status)
        entry = {
            "batch_id": found.batch_id,
            "enabled": found.enabled,
            "state": found.state.value,
            "mark": mark(found.state),
            "reason": found.reason,
        }
    if batch:
        session = RecoverySession(Path("."), batch, api=_NoCalls())
        session.status = status
        session.skipped = set(skip)
        built = session.view()
        view = {
            "batch": built.batch,
            "unknown_outcome": built.unknown_outcome,
            "rows": [row_payload(row) for row in built.rows],
            "blockers": list(built.blockers),
            "notes": list(built.notes),
            "actions": [action_payload(action) for action in built.actions],
        }
        resume = session.resume_plan()
        plan = {
            "command": resume.command,
            "checks": [[name, state] for name, state in resume.checks],
            "approval_required": resume.approval_required,
            "next_step": resume.next_step,
        }
    return {
        "history": [
            {"batch_id": item.batch_id, "label": item.label} for item in history.batches
        ],
        "history_unavailable": history.unavailable,
        "entry": entry,
        "view": view,
        "resume_plan": plan,
    }


def route_view_payload(
    authored: Authored,
    preflight: ApiResult | None,
    batch: str,
    role: str,
    runtime: str,
) -> dict[str, object]:
    """The selection, the executor context, the six stage tabs and every stage view of the
    container route, exactly as the TUI Container route screen builds them."""
    session = RouteSession(Path("."), api=_NoCalls(), load_authored=lambda _: authored)
    session.select(batch, role, runtime)
    session.preflight = preflight
    selection = session.selection
    return {
        "selection": {
            "batch": selection.batch,
            "role": selection.role,
            "runtime": selection.runtime,
        },
        "context": [[label, value] for label, value in session.executor_context()],
        "tabs": [
            {
                "stage": tab.stage.value,
                "title": tab.title,
                "state": tab.state.value,
                "mark": mark(tab.state),
                "reason": tab.reason,
            }
            for tab in session.tabs()
        ],
        "stages": {
            stage.value: stage_view_payload(session.view(stage)) for stage in Stage
        },
    }
