"""``resume``: re-check the batch, release its hold, react to the observed execution of its open
dispatches and continue a recorded stop through the audited ``batch resume-stop``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from harness.errors import HarnessError
from harness.orchestration import operational_hold
from harness.orchestration.core.constants import (
    LIVE_DISPATCH_STATES,
    TERMINAL_BATCH_STATES,
)
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.ledger.ledger_ops import _ledger_lock, read_state
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.recovery_status.batch_state import stopped_route
from harness.orchestration.recovery_status.intent import tracked
from harness.orchestration.recovery_status.model import (
    CHECKS,
    RECOVERY_CONTRACT,
    RecoveryDiagnostic,
)
from harness.orchestration.recovery_status.survey import Survey, open_entries


@dataclass
class _Run:
    """What one resume did, step by step; every step is safe to find again on a repeat."""

    steps: list[JsonObject] = field(default_factory=list)
    refused: list[RecoveryDiagnostic] = field(default_factory=list)

    def step(self, name: str, detail: str, **evidence: object) -> None:
        self.steps.append({"step": name, "detail": detail, **evidence})


def resume(
    repo: Path,
    root: Path,
    batch_id: str,
    *,
    approval: Mapping[str, str] | None = None,
) -> JsonObject:
    """Re-check ``batch_id``, release its hold and react to the observed execution of its open
    dispatches, then continue a recorded stop through the audited ``batch resume-stop`` when
    ``approval`` names the human, the time and the note.

    In one store unit every check of ``status`` runs first.  A refused check changes nothing,
    except that a batch whose record the strict read refuses is held in the store.  Otherwise
    the hold is released and the coordinator reacts to every open supervised dispatch as the
    runtime observes it: an ended execution gets its reaction, an unknown one is refused, and
    a live worker is never started a second time.  No approval, attention, budget, auto stop or
    terminal refusal is changed, no brief is rewritten and no dispatch is created: the next
    transition needs its own approval with the current digest."""
    run = _Run()
    with tracked(repo, root, batch_id, "resume") as intent:
        ledger = LifecycleLedger(root)
        with _ledger_lock(ledger):
            survey = Survey(repo, root, batch_id).run()
            refusals = [
                item
                for name in CHECKS
                if survey.checks[name].status == "refused"
                for item in survey.checks[name].diagnostics
                if item.fatal
            ]
            if refusals:
                run.refused.extend(refusals)
                _hold_unreadable(root, survey, run, refusals[0])
            else:
                _reconcile(repo, root, survey, run)
        if not run.refused and survey.batch is not None:
            _continue_stop(repo, root, batch_id, survey.batch, approval, run)
        outcome = "refused" if run.refused else "done"
        intent.finish(
            outcome, outcome, None if not run.refused else run.refused[0].message
        )
    with read_state(LifecycleLedger(root), repo):
        final = Survey(repo, root, batch_id).run()
        document = final.document()
        following = (
            _next_transition(root, final) if outcome == "done" else final.next_step()
        )
    return {
        "contract": RECOVERY_CONTRACT,
        "action": "resume",
        "batch_id": batch_id,
        "outcome": outcome,
        "steps": run.steps,
        "refusals": [item.to_dict() for item in run.refused],
        "dispatch_created": False,
        "worker_started": False,
        "status": document,
        "next": following,
    }


def _hold_unreadable(
    root: Path,
    survey: Survey,
    run: _Run,
    refusal: RecoveryDiagnostic,
) -> None:
    """Hold a batch whose record the strict read refuses, through its recovery record alone: no
    lifecycle record is written for it, and every command that would act on it stops on the
    hold.  A store that refused is not written either.  A readable batch is not held: the
    commands that repair it (dispatch cancel, attention resolve) keep working."""
    if (
        survey.batch is not None
        or survey.hold_reason is None
        or survey.checks["store"].status == "refused"
    ):
        return
    held = operational_hold.hold(root, survey.batch_id, survey.hold_reason, refusal.message)
    if held is not None:
        run.step(
            "hold",
            f"the batch is held ({held.reason}) until it reads and verifies again",
            hold=held.to_dict(),
        )


def _reconcile(repo: Path, root: Path, survey: Survey, run: _Run) -> None:
    """Release the hold, then react to the observed execution of every open supervised
    dispatch; the caller's store unit writes both."""
    from harness.orchestration.workflow import execution_reaction

    held = survey.hold
    if held is not None:
        operational_hold.release(root, survey.batch_id)
        run.step("release", f"the {held.reason} hold is released", hold=held.to_dict())
    for entry, dispatch in survey._briefs():
        if not execution_reaction.supervised(root, dispatch):
            continue
        try:
            execution = execution_reaction.observe(repo, root, entry["dispatch_id"])
        except HarnessError as exc:
            run.refused.append(RecoveryDiagnostic.from_error("operation", exc))
            return
        state = None if execution is None else execution.get("state")
        if state == "unknown":
            run.refused.append(
                RecoveryDiagnostic(
                    "ambiguous-effect",
                    "operation",
                    f"the runtime does not know whether the worker of {entry['dispatch_id']} "
                    "runs: nothing proves the outcome of its hand-off",
                    remedy="stop the worker, or wait until the runtime observes it again; a "
                    "live or unproved worker is never started a second time",
                )
            )
            return
        if state is not None and state not in execution_reaction.UNSETTLED_EXECUTION_STATES:
            run.step(
                "reconcile",
                f"the {state} execution of {entry['dispatch_id']} got its reaction",
                dispatch_id=entry["dispatch_id"],
                execution=state,
            )


def _continue_stop(
    repo: Path,
    root: Path,
    batch_id: str,
    batch: JsonObject,
    approval: Mapping[str, str] | None,
    run: _Run,
) -> None:
    """A recorded stop continues only through the audited ``batch resume-stop``."""
    import argparse

    from harness.orchestration.workflow.recovery import resume_stopped_batch

    route = stopped_route(batch)
    if route is None:
        return
    if route == "rewind" or approval is None:
        run.refused.append(
            RecoveryDiagnostic(
                "approval-required",
                "lifecycle",
                f"the {batch['state']} batch continues only through the audited {route}",
                remedy="repeat 'recovery resume' with --approved-by, --approved-at and --note"
                if route == "resume-stop"
                else "choose the gate with 'batch rewind --to <gate>' and a human approval",
            )
        )
        return
    try:
        result = resume_stopped_batch(
            argparse.Namespace(
                repo=str(repo),
                state_dir=str(root),
                batch=batch_id,
                approved_by=approval.get("approved_by"),
                approved_at=approval.get("approved_at"),
                note=approval.get("note"),
            )
        )
    except HarnessError as exc:
        run.refused.append(RecoveryDiagnostic.from_error("lifecycle", exc))
        return
    event = result.get("event")
    run.step(
        "resume-stop",
        "the recorded stop continues through the audited resume-stop event",
        event_sequence=event.get("sequence") if isinstance(event, dict) else None,
        state=result.get("state"),
    )


def _next_transition(root: Path, survey: Survey) -> JsonObject | None:
    """The command that continues the batch; a new transition needs its own approval."""
    from harness.orchestration.core.constants import NEXT_ACTION_DISPATCH_ROLE
    from harness.orchestration.ledger.ledger_ops import _load_dispatch_status

    batch = survey.batch
    if batch is None:
        return None
    for entry in open_entries(batch):
        dispatch_id = entry["dispatch_id"]
        state = _load_dispatch_status(root, dispatch_id).get("state")
        if entry.get("state") == "approved" and state == "approved":
            command = (
                f"qa run --dispatch {dispatch_id}"
                if entry.get("role") == "qa"
                else f"dispatch send --dispatch {dispatch_id}"
            )
            return {"command": command, "reason": "the approved brief was never sent"}
        if entry.get("state") == "reported":
            return {
                "command": f"batch decision-packet --batch {batch['batch_id']}",
                "reason": "a completion report awaits its decision",
            }
        if state in LIVE_DISPATCH_STATES:
            return {
                "command": f"dispatch wait --dispatch {dispatch_id}",
                "reason": "a worker may still run; no second one is started",
            }
    action = str(batch.get("next_action"))
    # A recovered stage names its role itself (``developer`` after a resume-stop).
    role = NEXT_ACTION_DISPATCH_ROLE.get(
        action, action if action in {"developer", "architect"} else None
    )
    if role is None or batch.get("state") in TERMINAL_BATCH_STATES:
        return None
    purpose = " --purpose publish" if action == "publish" else ""
    return {
        "command": f"dispatch propose --batch {batch['batch_id']} --role {role}{purpose}",
        "reason": "the next transition needs an approval with its current digest",
    }
