"""The checks of the evidence the batch's commands run on: the harness runtime, the pinned
configuration snapshots, the Context Packages of the open briefs and the runtime compatibility."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, cast

from harness.errors import INTERNAL_INVARIANT_REMEDY, HarnessError
from harness.orchestration.core.utils import JsonObject, _canonical
from harness.orchestration.recovery.model import RecoveryDiagnostic
from harness.orchestration.recovery.runtime import (
    RECOVERY_FEATURES,
    RECOVERY_PROTOCOL,
    runtime_problems,
)

if TYPE_CHECKING:
    from harness.orchestration.recovery.survey import Survey


def check_runtime(survey: Survey) -> None:
    """The harness runtime the batch's commands run on: the installed one, or the verified
    pinned snapshot they hand themselves to; recovery itself runs on the installed one."""
    from harness.orchestration.core import workspace
    from harness.orchestration.workflow.runtime_pin import _pinned_hash

    batch = cast(JsonObject, survey.batch)
    check = survey.checks["runtime"]
    pinned = _pinned_hash(batch)
    runs_on: str | None = "installed"
    try:
        workspace._validate_harness_runtime_snapshot(survey.repo, batch)
    except HarnessError as exc:
        refusal, runs_on = exc, None
        try:
            if (
                pinned is not None
                and workspace._pinned_runtime_entry(survey.root, pinned) is not None
            ):
                runs_on = "pinned-snapshot"
        except HarnessError as snapshot:
            refusal = snapshot
        if runs_on is None:
            check.add(
                RecoveryDiagnostic.from_error("runtime", refusal), status="refused"
            )
    check.evidence = {"pinned": pinned, "runs_on": runs_on}


def check_context(survey: Survey) -> None:
    """Every open brief's Context Package verifies and still matches the batch's base and
    current developer candidate, by the rule the stale-evidence attention applies."""
    from harness.orchestration.ledger.ledger_ops import _load_context_package
    from harness.orchestration.workflow.history import (
        _current_developer_candidate,
        _effective_base,
        _pinned_package_stale,
        _validate_context_package,
    )

    batch = cast(JsonObject, survey.batch)
    check = survey.checks["context"]
    briefs = [
        (entry, dispatch)
        for entry, dispatch in survey._briefs()
        if isinstance(dispatch.get("context_package_id"), str)
    ]
    evidence: list[JsonObject] = []
    try:
        current_base = _effective_base(batch)
        current_candidate = (
            _current_developer_candidate(survey.repo, survey.root, batch)
            if briefs
            else None
        )
        for entry, dispatch in briefs:
            dispatch_id = dispatch["dispatch_id"]
            location = f"/dispatches/{dispatch_id}/context_package_id"
            package = _load_context_package(
                survey.root, dispatch["context_package_id"]
            )
            _validate_context_package(survey.root, batch, package)
            digest = hashlib.sha256(_canonical(package).encode("utf-8")).hexdigest()
            if digest != dispatch.get("context_package_sha256"):
                check.add(
                    RecoveryDiagnostic(
                        "integrity-failure",
                        "context",
                        f"dispatch {dispatch_id}: its Context Package does not match the "
                        "hash its brief pinned",
                        remedy=INTERNAL_INVARIANT_REMEDY,
                        location=location,
                    ),
                    status="refused",
                )
                continue
            stale = entry.get("state") != "reported" and _pinned_package_stale(
                survey.repo, survey.root, batch, dispatch
            )
            pinned = {
                "base_commit": package["base_commit"],
                "candidate_commit": package["candidate_commit"],
            }
            evidence.append(
                {
                    "dispatch_id": dispatch_id,
                    "context_package_id": package["context_package_id"],
                    **pinned,
                    "stale": stale,
                }
            )
            if stale:
                check.add(
                    RecoveryDiagnostic(
                        "stale-evidence",
                        "context",
                        f"dispatch {dispatch_id} pins a Context Package older than the "
                        "batch's base or current developer candidate",
                        remedy="cancel the brief with dispatch cancel and propose a new "
                        "dispatch so a fresh Context Package is pinned; the brief is "
                        "never rewritten",
                        location=location,
                        expected={
                            "base_commit": current_base,
                            "candidate_commit": current_candidate,
                        },
                        received=pinned,
                    ),
                    status="refused",
                )
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("context", exc), status="refused")
        return
    check.evidence = {
        "current_base": current_base,
        "current_candidate": current_candidate,
        "briefs": evidence,
    }


def check_snapshot(survey: Survey) -> None:
    from harness.orchestration.pinned_configuration import read_snapshot

    check = survey.checks["snapshot"]
    pinned = []
    for _, dispatch in survey._briefs():
        policy = dispatch.get("orchestration_policy")
        if not isinstance(policy, dict) or "configuration" not in policy:
            continue
        try:
            read_snapshot(dispatch)
        except HarnessError as exc:
            check.add(
                RecoveryDiagnostic(
                    "integrity-failure",
                    "snapshot",
                    f"dispatch {dispatch['dispatch_id']}: {exc.message}",
                    remedy=f"{exc.remedy}; or cancel the unsent brief with dispatch "
                    "cancel and propose a new one",
                    location=f"/dispatches/{dispatch['dispatch_id']}/orchestration_policy"
                    "/configuration",
                ),
                status="refused",
            )
            continue
        pinned.append(dispatch["dispatch_id"])
    check.evidence = {"pinned": pinned}


def check_compatibility(survey: Survey) -> None:
    """The runtime this coordinator talks to keeps the recovery records: the protocol, the
    store and the features of its hello."""
    check = survey.checks["compatibility"]
    if survey.hello is None:
        survey._skip("compatibility", "the runtime hello is not readable")
        return
    check.evidence = dict(survey.hello)
    problems = runtime_problems(survey.hello)
    if problems:
        check.add(
            RecoveryDiagnostic(
                "runtime-compatibility",
                "compatibility",
                f"the runtime cannot keep the recovery records: {'; '.join(problems)}",
                remedy="update harness-runtime to the version of this harness and restart "
                "it, then run 'recovery reload'",
                expected={
                    "protocol": {
                        "major": RECOVERY_PROTOCOL[0],
                        "minor": RECOVERY_PROTOCOL[1],
                    },
                    "features": list(RECOVERY_FEATURES),
                },
                received={
                    "protocol": survey.hello.get("protocol"),
                    "features": survey.hello.get("features"),
                },
            ),
            status="refused",
        )
