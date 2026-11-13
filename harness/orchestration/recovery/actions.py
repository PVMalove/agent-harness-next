"""The recovery actions besides ``resume``: ``status``, ``reload``, ``fix``, ``skip`` and
``abort``."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from harness.configuration import Bundle, bundle_diff
from harness.configuration_store import ConfigurationStore, json_bytes
from harness.orchestration.core.utils import CoordinatorError, JsonObject
from harness.orchestration.ledger.ledger_ops import read_state, store_is_authority
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.operational_hold import FILE_EPOCH_REMEDY
from harness.orchestration.recovery.batch_state import lifecycle_view
from harness.orchestration.recovery.intent import read_intent, tracked
from harness.orchestration.recovery.model import (
    ADVISORIES,
    RECOVERY_CONTRACT,
    RecoveryDiagnostic,
    RecoverySession,
)
from harness.orchestration.recovery.runtime import runtime_hello, runtime_problems
from harness.orchestration.recovery.survey import Survey


def _require_store_epoch(root: Path) -> None:
    if not store_is_authority(root):
        raise CoordinatorError(
            "recovery runs on the runtime store; this repository is in the file-ledger epoch",
            remedy=FILE_EPOCH_REMEDY,
        )


def status(
    repo: Path, root: Path, batch_id: str, *, session: RecoverySession | None = None
) -> JsonObject:
    """The read-only recovery status of ``batch_id``: it takes no lock and writes nothing."""
    _require_store_epoch(root)
    with read_state(LifecycleLedger(root), repo):
        return Survey(repo, root, batch_id).run().document(session)


def reload(repo: Path, root: Path, batch_id: str) -> JsonObject:
    """Re-read and validate the current configuration and the runtime hello; never starts a
    worker."""
    with tracked(repo, root, batch_id, "reload") as intent:
        survey = Survey(repo, root, batch_id)
        survey._config()
        check = survey.checks["config"]
        hello = runtime_hello(repo)
        problems = runtime_problems(hello)
        refused = check.status == "refused" or bool(problems)
        outcome = "refused" if refused else "done"
        intent.finish(outcome, outcome, "; ".join(problems) or None)
        return {
            "contract": RECOVERY_CONTRACT,
            "action": "reload",
            "batch_id": batch_id,
            "outcome": outcome,
            "config": check.evidence,
            "diagnostics": [item.to_dict() for item in check.diagnostics],
            "runtime": {**hello, "compatible": not problems, "problems": problems},
            "worker_started": False,
            "next": {"command": f"recovery resume --batch {batch_id}"}
            if outcome == "done"
            else {"command": "config validate --fix --dry-run"}
            if survey.fix_available()
            else None,
        }


def fix(repo: Path, root: Path, batch_id: str, *, apply: bool = False) -> JsonObject:
    """Preview, or with ``apply`` write through the configuration transaction, the safe
    normalization of the current configuration; nothing is resumed."""
    with tracked(repo, root, batch_id, "fix") as intent:
        survey = Survey(repo, root, batch_id)
        survey._config()
        check = survey.checks["config"]
        result: JsonObject = {
            "contract": RECOVERY_CONTRACT,
            "action": "fix",
            "batch_id": batch_id,
            "diagnostics": [item.to_dict() for item in check.diagnostics],
            "diff": None,
            "applied": False,
            "backup_version": None,
            "resumed": False,
            "next": {"command": f"recovery reload --batch {batch_id}"},
        }
        document = survey.config_document
        if not survey.fix_available() or survey.bundle is None or document is None:
            result["outcome"] = "refused" if check.status == "refused" else "done"
            intent.finish(result["outcome"], result["outcome"], "nothing to normalize")
            return result
        changes: Bundle = {"orchestration.json": json_bytes(document)}
        result["diff"] = bundle_diff(
            {"orchestration.json": survey.bundle["orchestration.json"]},
            changes,
            "current",
            "canonical",
        )
        if apply:
            try:
                backup = ConfigurationStore(repo).apply(changes, expected=survey.bundle)
            except (ValueError, OSError) as exc:
                result["diagnostics"].append(
                    RecoveryDiagnostic(
                        "config-invalid",
                        "config",
                        f"the configuration transaction refused the write: {exc}",
                        remedy="run 'recovery reload' and preview the fix again",
                    ).to_dict()
                )
                result["outcome"] = "refused"
                intent.finish("refused", "refused", str(exc))
                return result
            result.update({"applied": True, "backup_version": backup.id})
        result["outcome"] = "done"
        intent.finish("done", "done", "applied" if apply else "previewed")
        return result


def skip(
    session: RecoverySession, document: JsonObject, diagnostic_id: str
) -> RecoverySession:
    """Hide one allowlisted advisory of ``document`` for this session only; a fatal or
    unlisted diagnostic is refused, and nothing is written."""
    found = next(
        (
            item
            for item in cast(list[JsonObject], document.get("diagnostics", []))
            if item.get("id") == diagnostic_id
        ),
        None,
    )
    if found is None:
        raise CoordinatorError(
            f"no diagnostic {diagnostic_id} in this recovery status",
            remedy="select a diagnostic the current status lists",
        )
    if found.get("fatal") is not False or found.get("advisory") not in ADVISORIES:
        raise CoordinatorError(
            f"diagnostic {diagnostic_id} ({found.get('code')}) is not a skippable advisory",
            remedy="only an allowlisted advisory is hidden; schema, enum, integrity, "
            "compatibility, evidence and approval diagnostics are resolved, never skipped",
        )
    return RecoverySession(session.skipped | {diagnostic_id})


def abort(repo: Path, root: Path, batch_id: str) -> JsonObject:
    """Record that the operator left recovery and flush that intent; the batch, its workers
    and its worktree stay exactly as they are."""
    with tracked(repo, root, batch_id, "abort") as intent:
        intent.finish("aborted", "done", "the operator left recovery")
    survey = Survey(repo, root, batch_id)
    with read_state(LifecycleLedger(root), repo):
        survey._store()
        survey._batch()
        intent_record = read_intent(root, batch_id)
    return {
        "contract": RECOVERY_CONTRACT,
        "action": "abort",
        "batch_id": batch_id,
        "outcome": "done",
        "lifecycle": None if survey.batch is None else lifecycle_view(survey.batch),
        "hold": None if survey.hold is None else survey.hold.to_dict(),
        "abandoned": False,
        "worker_stopped": False,
        "worktree_cleaned": False,
        "intent": intent_record,
    }
