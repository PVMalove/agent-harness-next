"""View-model of the container executor route: six stages (Setup, Preflight, Plan / approval, Worker,
QA, Cleanup) over the structured coordinator client. Textual-free like the rest of the console seam.

The model owns no rule of the core: every fact comes from a document the coordinator CLI printed
(`dispatch preflight`, `propose`, `create`, `status`, `qa run`/`status`, `harness cleanup`), shown as it
is. What the core did not report is shown as `не проверено` or `не сообщается`, never as a success.
Choosing a stage only selects which view is drawn; each external effect is an `Action` a screen
runs on an explicit button, and an action that cannot run carries its visible `reason`. Environment
variables appear by name only; no value ever reaches a row, an argv or a log.

The package keeps the model in `model`, the authored configuration in `config`, one module per
stage view (`setup_stage`, `preflight_stage`, `plan_stage`, `worker_stage`, `qa_stage`,
`cleanup_stage`) and the operator's `RouteSession` in `session`; this module re-exports their
public names.
"""

from __future__ import annotations

from .cleanup_stage import (
    CONTAINER_KINDS,
    LIVE_EXECUTION_STATES,
    CleanupState,
    cleanup_view,
    plan_digest_of,
)
from .config import Authored, read_authored
from .model import (
    CONFIRMED_EFFECTS,
    NEED_BATCH,
    STAGE_TITLES,
    STATE_MARKS,
    Action,
    Effect,
    JsonObject,
    Row,
    Selection,
    Stage,
    StageView,
    State,
    Tab,
    env_names,
    mark,
)
from .plan_stage import Proposal, plan_view
from .preflight_stage import preflight_tab_state, preflight_view, verification_status
from .qa_stage import QaState, qa_view
from .session import RouteSession, read_report
from .setup_stage import authored_rows, setup_view
from .worker_stage import worker_entry, worker_view

__all__ = [
    "CONFIRMED_EFFECTS",
    "CONTAINER_KINDS",
    "LIVE_EXECUTION_STATES",
    "NEED_BATCH",
    "STAGE_TITLES",
    "STATE_MARKS",
    "Action",
    "Authored",
    "CleanupState",
    "Effect",
    "JsonObject",
    "Proposal",
    "QaState",
    "RouteSession",
    "Row",
    "Selection",
    "Stage",
    "StageView",
    "State",
    "Tab",
    "authored_rows",
    "cleanup_view",
    "env_names",
    "mark",
    "plan_digest_of",
    "plan_view",
    "preflight_tab_state",
    "preflight_view",
    "qa_view",
    "read_authored",
    "read_report",
    "setup_view",
    "verification_status",
    "worker_entry",
    "worker_view",
]
