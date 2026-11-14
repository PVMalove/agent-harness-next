"""Publishing an accepted candidate: the push of an approved publish-only brief.

`delivery.py` hands every other brief to a transport; a publish-only brief never reaches one. Here
the coordinator itself pushes exactly the QA-accepted candidate, after the Release Gate, the
strict hook boundary and the pinned operation access allow it, and records the publication.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from harness.orchestration import hook_policy, operation_access, operational_hold
from harness.orchestration.core import config as core_config
from harness.orchestration.core import utils
from harness.orchestration.core.git_utils import (
    _changed_files_between,
    _commit_changed_files,
    _git,
    _remote_branch_tip,
    git_environment,
    git_failure,
)
from harness.orchestration.core.utils import (
    CoordinatorError,
    JsonObject,
    _non_empty,
    _repo,
    _safe_id,
    _sanitise,
)
from harness.orchestration.infrastructure_retry import (
    pinned,
    record_operation_failure,
    require_publish_destination,
    stop_attention,
)
from harness.orchestration.ledger.ledger_ops import (
    _ledger_lock,
    _load_batch,
    _load_dispatch,
    _load_dispatch_status,
    _replace_record,
    _state_root,
)
from harness.orchestration.ledger.lifecycle import (
    BatchRecord,
    DispatchStatusRecord,
    LifecycleLedger,
)
from harness.orchestration.workflow import rebase, release_gate
from harness.orchestration.workflow.history import (
    _accepted_qa_for_candidate,
    _validate_batch_integrity,
    _validate_dispatch,
)
from harness.orchestration.workflow.reports import _persist_report

# A push of one already verified commit is bounded; the limit only stops a hung transport.
PUBLISH_PUSH_TIMEOUT_SECONDS = 600


def _record_publish_pair(
    repo: Path, root: Path, ledger: LifecycleLedger, dispatch_id: str
) -> None:
    """Record the Release Gate pair of a publish with accepted QA before its push is decided.

    A block of its own: in the runtime-store epoch the pair is in the store before the runtime
    judges its evidence. Anything else this block finds wrong is left to the publish checks,
    which refuse it with their own remedy."""
    with _ledger_lock(ledger):
        dispatch = _load_dispatch(root, dispatch_id)
        if dispatch.get("purpose") != "publish":
            return
        batch = _load_batch(root, dispatch["batch_id"])
        try:
            _accepted_qa_for_candidate(root, batch, dispatch["candidate_commit"])
        except CoordinatorError:
            return
        pair = release_gate.publish_pair(batch, dispatch)
        release_gate.record_pair(
            ledger,
            repo,
            pair["candidate_sha"],
            pair["target_sha"],
            release_gate.required_selection(repo, batch),
        )


def publish_dispatch(args: argparse.Namespace) -> JsonObject:
    """Push one QA-accepted candidate through an approved publish-only brief."""
    repo = _repo(args)
    root = _state_root(args, repo)
    remote = _publish_remote(repo, args.remote)
    ledger = LifecycleLedger(root)
    _record_publish_pair(repo, root, ledger, args.dispatch)
    with _ledger_lock(ledger):
        dispatch, batch, entry = _approved_publish(repo, root, args.dispatch)
        try:
            require_publish_destination(repo, root, dispatch, remote)
        except CoordinatorError as exc:
            stop_attention(repo, root, args.dispatch, exc, locked=True)
            raise
        candidate = dispatch["candidate_commit"]
        _require_release_boundaries(repo, root, batch, dispatch, candidate)
        access = _publish_access(repo, root, dispatch, remote)
        _push_candidate(repo, remote, candidate, dispatch["branch"])
        report_path = _record_publication(
            ledger, repo, root, batch, dispatch, entry, candidate, remote
        )
    return {
        "dispatch_id": dispatch["dispatch_id"],
        "state": "reported",
        "report": str(report_path),
        "candidate_commit": candidate,
        "access": access,
    }


def _publish_remote(repo: Path, value: object) -> str:
    """The named publish remote, refused unless it is configured for this repository."""
    remote = value.strip() if _non_empty(value) else ""
    if not remote:
        raise CoordinatorError(
            "publish remote must be a non-empty string",
            remedy="pass --remote as a non-empty string",
        )
    if remote not in _git(repo, "remote").splitlines():
        raise CoordinatorError(
            "publish remote is not configured for this repository",
            remedy="add the named remote to this repository (git remote add) before publishing",
        )
    return remote


def _approved_publish(
    repo: Path, root: Path, dispatch_id: str
) -> tuple[JsonObject, JsonObject, JsonObject]:
    """The approved, unsent publish-only dispatch, its batch and its batch entry, under the lock."""
    dispatch = _load_dispatch(root, dispatch_id)
    batch = _load_batch(root, dispatch["batch_id"])
    operational_hold.require_no_hold(root, dispatch["batch_id"])
    _validate_batch_integrity(root, batch)
    _validate_dispatch(repo, core_config._config(repo), root, batch, dispatch)
    if dispatch["purpose"] != "publish":
        raise CoordinatorError(
            "only a publish-only dispatch may push a candidate",
            remedy="only a publish-only dispatch may push a candidate",
        )
    status = _load_dispatch_status(root, dispatch["dispatch_id"])
    entry = next(
        (
            item
            for item in batch["dispatches"]
            if item["dispatch_id"] == dispatch["dispatch_id"]
        ),
        None,
    )
    if (
        not entry
        or entry.get("state") != "approved"
        or status.get("state") != "approved"
    ):
        raise CoordinatorError(
            "publish requires an approved, unsent publish-only dispatch",
            remedy="approve a publish-only dispatch, and send it, before publishing",
        )
    return dispatch, batch, entry


def _require_release_boundaries(
    repo: Path, root: Path, batch: JsonObject, dispatch: JsonObject, candidate: str
) -> None:
    """Accepted QA, the Release Gate and the strict hook boundary of the candidate."""
    accepted_qa = _accepted_qa_for_candidate(root, batch, candidate)
    # The Release Gate (ADR 0026, section 4): in the runtime-store epoch nothing is pushed
    # unless the runtime confirms a full QA run of exactly the pair this push publishes.
    release_gate.require_evidence(
        repo, root, release_gate.publish_pair(batch, dispatch)
    )
    # Strict fails closed before the push: the plan is the one the accepted QA brief carried.
    hook_policy.check_strict_boundary(
        repo,
        hook_policy.dispatch_policy(dispatch),
        role="coordinator",
        boundary="publish",
        batch=batch,
        candidate=candidate,
        plan=_load_dispatch(root, accepted_qa["dispatch_id"]).get("verification_plan"),
    )


def _publish_access(
    repo: Path, root: Path, dispatch: JsonObject, remote: str
) -> JsonObject:
    """The proven operation access of the push; a refusal is recorded for a pinned retry."""
    # Only a candidate with accepted QA reaches this check, and nothing leaves the machine
    # before the pinned plan of this brief is proven for Git metadata, storage and the remote.
    try:
        return operation_access.require(
            repo,
            core_config._config(repo),
            "publish",
            brief=dispatch,
            remote=remote,
        )
    except operation_access.OperationAccessError as exc:
        policy = pinned(dispatch)
        if policy and policy["enabled"]:
            record_operation_failure(
                repo, root, dispatch, "publish", exc.evidence, remote, locked=True
            )
        raise


def _push_candidate(repo: Path, remote: str, candidate: str, branch: str) -> None:
    """Push exactly the candidate to the remote branch and read the branch back."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "push",
                remote,
                f"{candidate}:refs/heads/{branch}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            env=git_environment(),
            timeout=PUBLISH_PUSH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        # The ledger is unchanged, and a repeated push of the same commit is a no-op.
        raise CoordinatorError(
            f"git push to {remote!r} did not finish within "
            f"{PUBLISH_PUSH_TIMEOUT_SECONDS} seconds",
            remedy=f"check connectivity to {remote!r} and repeat dispatch publish; the "
            "dispatch stays approved",
        ) from exc
    except OSError as exc:
        raise CoordinatorError(
            f"git push could not be started: {exc}",
            remedy="make git available on PATH and repeat dispatch publish",
        ) from exc
    if result.returncode != 0:
        detail = _sanitise((result.stderr or result.stdout).strip())
        raise git_failure(
            f"could not publish the accepted candidate: {detail or 'unknown error'}",
            detail,
            remedy="inspect the git push error above and fix it before retrying publish",
        )
    # Bounded and exact: an ls-remote pattern also matches deeper names ending in the branch.
    if _remote_branch_tip(repo, remote, branch) != candidate:
        raise CoordinatorError(
            "remote branch does not resolve to the accepted QA candidate",
            remedy="push exactly the accepted QA candidate commit to the remote branch",
        )


def _record_publication(
    ledger: LifecycleLedger,
    repo: Path,
    root: Path,
    batch: JsonObject,
    dispatch: JsonObject,
    entry: JsonObject,
    candidate: str,
    remote: str,
) -> Path:
    """Mark the pushed dispatch sent and persist the publication report it completes."""
    entry["state"] = "dispatched"
    _safe_id(dispatch["dispatch_id"], "dispatch")
    _replace_record(
        ledger,
        DispatchStatusRecord.from_dict(
            {
                "dispatch_id": dispatch["dispatch_id"],
                "state": "dispatched",
                "updated_at": utils._now(),
            }
        ),
    )
    _safe_id(batch["batch_id"], "batch")
    _replace_record(ledger, BatchRecord.from_dict(batch))
    base = rebase.batch_base(repo, batch)
    changed = (
        _changed_files_between(repo, base, candidate)
        if base
        else _commit_changed_files(repo, candidate)
    )
    report = {
        "dispatch_id": dispatch["dispatch_id"],
        "ticket": dispatch["ticket"],
        "role": "developer",
        "outcome": "completed",
        "output": f"published accepted QA candidate {candidate} to {remote}/{dispatch['branch']}",
        "commit_sha": candidate,
        "changed_files": changed,
        "checks_run": [
            {
                "command": command,
                "result": "pass",
                "evidence": f"accepted clean-room QA evidence for {candidate}",
            }
            for command in dispatch["verification_commands"]
        ],
        "risks": {"status": "none", "details": ""},
        "blockers": {"status": "none", "details": ""},
        "next_coordinator_action": "accept publication or inspect remote evidence",
        "report_language": "ru",
    }
    return _persist_report(ledger, root, batch, dispatch, report)
