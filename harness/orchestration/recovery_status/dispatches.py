"""The checks of the open dispatches: the observed execution of each supervised one, the
workers that may still run and the approvals of the unsent briefs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from harness.errors import HarnessError
from harness.orchestration.core.constants import LIVE_DISPATCH_STATES
from harness.orchestration.core.utils import JsonObject, _moment, _silent_seconds
from harness.orchestration.recovery_status.model import RecoveryDiagnostic

if TYPE_CHECKING:
    from harness.orchestration.recovery_status.survey import Survey


def check_operation(survey: Survey) -> None:
    """The observed execution of every open supervised dispatch: an ended one is the
    reaction resume applies, an unknown one an effect nothing proves."""
    from harness.orchestration.workflow import execution_reaction
    from harness.orchestration.workflow.delivery import observed_execution

    check = survey.checks["operation"]
    if survey.batch is None:
        return
    observed: list[JsonObject] = []
    try:
        for entry, dispatch in survey._briefs():
            if not execution_reaction.supervised(survey.root, dispatch):
                continue
            execution = observed_execution(survey.repo, entry["dispatch_id"])
            state = None if execution is None else execution.get("state")
            observed.append({"dispatch_id": entry["dispatch_id"], "execution": state})
            if state == "unknown":
                check.add(
                    RecoveryDiagnostic(
                        "ambiguous-effect",
                        "operation",
                        f"the runtime does not know whether the worker of "
                        f"{entry['dispatch_id']} runs: resume refuses instead of starting "
                        "a second one",
                        remedy="stop the worker, or wait until the runtime observes it "
                        "again; a live or unproved worker is never started a second time",
                        severity="warning",
                    ),
                    status="pending",
                )
            elif state is not None and (
                state not in execution_reaction.UNSETTLED_EXECUTION_STATES
            ):
                check.detail = (
                    "an ended execution: resume applies the reaction of the observed exit"
                )
                check.set("pending")
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("operation", exc), status="refused")
    check.evidence = {"executions": observed}


def check_liveness(survey: Survey) -> None:
    from harness.orchestration.ledger.ledger_ops import _load_dispatch_status

    check = survey.checks["liveness"]
    live = []
    for entry, _ in survey._briefs():
        status = _load_dispatch_status(survey.root, entry["dispatch_id"])
        if status.get("state") not in LIVE_DISPATCH_STATES:
            continue
        silent = _silent_seconds(status)
        live.append({"dispatch_id": entry["dispatch_id"], "silent_seconds": silent})
        check.add(
            RecoveryDiagnostic(
                "live-worker",
                "liveness",
                f"the worker of {entry['dispatch_id']} may still run (silent {silent}s): "
                "resume starts no worker and creates no dispatch for it",
                remedy="wait for its report, or stop it and run dispatch cancel "
                "--runtime-stopped with an approval",
                severity="warning",
            )
        )
    check.evidence = {"live": live}


def check_approval(survey: Survey) -> None:
    check = survey.checks["approval"]
    for entry, dispatch in survey._briefs():
        if entry.get("state") != "approved":
            continue
        policy = dispatch.get("orchestration_policy")
        ttl = (survey.config or {}).get("approval_ttl_seconds")
        if ttl is None and isinstance(policy, dict):
            ttl = policy.get("approval_ttl_seconds")
        approval = dispatch.get("coordinator_approval")
        approved_at = (
            approval.get("approved_at") if isinstance(approval, dict) else None
        )
        if isinstance(ttl, int) and isinstance(approved_at, str):
            age = (
                datetime.now(UTC) - _moment(approved_at, "approved-at")
            ).total_seconds()
            if age > ttl:
                check.add(
                    RecoveryDiagnostic(
                        "approval-stale",
                        "approval",
                        f"the approval of the unsent {dispatch['dispatch_id']} is "
                        f"{int(age)}s old and approval_ttl_seconds is {ttl}",
                        remedy="cancel the unsent brief with dispatch cancel and approve "
                        "a new proposal with its current transition digest; an expired "
                        "approval is never reused",
                    ),
                    status="refused",
                )
        snapshot = policy.get("configuration") if isinstance(policy, dict) else None
        if (
            survey.config is not None
            and isinstance(snapshot, dict)
            and snapshot.get("config") != dict(survey.config)
        ):
            check.add(
                RecoveryDiagnostic(
                    "approval-required",
                    "approval",
                    f"the configuration changed since {dispatch['dispatch_id']} was "
                    "approved: the brief keeps its approved snapshot",
                    remedy="the next transition needs an approval with the digest "
                    "'dispatch propose' prints under the current configuration",
                    severity="warning",
                )
            )
