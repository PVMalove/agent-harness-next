"""The checks of the batch record itself: its lifecycle state and its open attention."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from harness.orchestration.core.constants import TERMINAL_BATCH_STATES
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.recovery_status.model import RecoveryDiagnostic

if TYPE_CHECKING:
    from harness.orchestration.recovery_status.survey import Survey


def check_lifecycle(survey: Survey) -> None:
    """The batch's lifecycle state: a terminal batch is refused, a recorded stop waits for the
    audited route that resumes it with a human approval."""
    batch = cast(JsonObject, survey.batch)
    check = survey.checks["lifecycle"]
    check.evidence = lifecycle_view(batch)
    if batch["state"] in TERMINAL_BATCH_STATES:
        check.add(
            RecoveryDiagnostic(
                "terminal-refusal",
                "lifecycle",
                f"the batch is {batch['state']}: a terminal batch is never resumed",
                remedy="create a new batch for further work; its history stays as it is",
            ),
            status="refused",
        )
    elif (route := stopped_route(batch)) is not None:
        check.evidence = {**check.evidence, "route": route}
        remedy = (
            "run 'recovery resume' with --approved-by, --approved-at and --note: it "
            "records the audited batch resume-stop"
            if route == "resume-stop"
            else "choose the gate to continue from with 'batch rewind --to <gate>' and a "
            "human approval; recovery never picks it"
        )
        check.add(
            RecoveryDiagnostic(
                "approval-required",
                "lifecycle",
                f"the batch is {batch['state']}: its recorded stop is resumed only through "
                f"the audited {route} with a human approval",
                remedy=remedy,
                severity="warning",
            ),
            status="pending",
        )


def check_attention(survey: Survey) -> None:
    """The batch's open attention: recovery never resolves it, so an open one is refused."""
    batch = cast(JsonObject, survey.batch)
    check = survey.checks["attention"]
    if batch.get("needs_attention") is True:
        check.add(
            RecoveryDiagnostic(
                "attention-open",
                "attention",
                f"the batch needs human attention ({batch.get('attention_reason')}): "
                "recovery never resolves it",
                remedy=f"{batch.get('recommended_human_action')}; resolve it with "
                f"'batch attention resolve --batch {survey.batch_id}' before 'recovery "
                "resume'",
            ),
            status="refused",
        )
    check.evidence = {
        "needs_attention": bool(batch.get("needs_attention", False)),
        "attention_reason": batch.get("attention_reason"),
    }


def stopped_route(batch: JsonObject) -> str | None:
    from harness.orchestration.workflow import recovery

    return recovery.stopped_route(batch)


def lifecycle_view(batch: JsonObject) -> JsonObject:
    """The lifecycle facts recovery preserves and shows; it never changes them itself."""
    from harness.orchestration.workflow.recovery import STOPPED_STATES

    return {
        "state": batch["state"],
        "next_action": batch.get("next_action"),
        "terminal": batch["state"] in TERMINAL_BATCH_STATES,
        "stopped": batch["state"] in STOPPED_STATES,
        "needs_attention": bool(batch.get("needs_attention", False)),
        "attention_reason": batch.get("attention_reason"),
        "auto_stop": batch.get("auto_stop") is not None,
        "manual_recovery": bool(batch.get("manual_recovery", False)),
    }
