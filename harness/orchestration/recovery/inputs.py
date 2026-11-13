"""The inputs of the survey: the configuration, the store with the hold, the ledger and the
batch record.  Each read keeps what the later checks need on the survey."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from harness.configuration import read_config_bundle
from harness.errors import HarnessError
from harness.orchestration import operational_hold
from harness.orchestration.config_boundary import inspect_configuration
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.ledger.ledger_ops import _read_store_record
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.operational_hold import sanitize_detail
from harness.orchestration.recovery.model import RecoveryDiagnostic
from harness.orchestration.recovery.runtime import runtime_hello

if TYPE_CHECKING:
    from harness.orchestration.recovery.survey import Survey


def read_config(survey: Survey) -> None:
    check = survey.checks["config"]
    try:
        survey.bundle = read_config_bundle(survey.repo)
    except (ValueError, OSError) as exc:
        check.add(
            RecoveryDiagnostic(
                "config-invalid",
                "config",
                f"the configuration cannot be read: {exc}",
                remedy="repair .harness/orchestration.json, then run 'recovery reload'",
            ),
            status="refused",
        )
        return
    result = inspect_configuration(survey.repo, survey.bundle["orchestration.json"])
    for item in result.diagnostics:
        check.add(RecoveryDiagnostic.from_config(item))
    check.evidence = {
        "valid": result.valid,
        "source_sha256": result.source_sha256,
        "normalizer": result.to_dict()["normalizer"],
    }
    if not result.valid:
        check.set("refused")
        return
    survey.config_document = result.document
    from harness.orchestration.core import config as core_config

    try:
        survey.config = core_config._config(survey.repo)
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("config", exc), status="refused")


def read_store(survey: Survey) -> None:
    """The runtime hello and the hold record of the batch: whether the store holds it."""
    check = survey.checks["store"]
    try:
        survey.hello = runtime_hello(survey.repo)
        survey.hold = operational_hold.current_hold(survey.root, survey.batch_id)
        _, revision = _read_store_record(
            survey.root, operational_hold.hold_relative(survey.batch_id)
        )
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("store", exc), status="refused")
        return
    check.evidence = {
        "store_id": survey.hello["store_id"],
        "hold_revision": revision,
        "hold": None if survey.hold is None else survey.hold.reason,
    }
    if survey.hold is None:
        return
    held = survey.hold
    diagnostic = RecoveryDiagnostic(
        "integrity-failure",
        "store",
        f"the runtime store holds the batch ({held.reason}): {held.message}",
        remedy=held.remedy,
        severity="error",
    )
    check.add(diagnostic, status="pending" if held.releasable else "refused")


def read_ledger(survey: Survey) -> None:
    from harness.orchestration.ledger.ledger_ops import _ledger_errors

    check = survey.checks["ledger"]
    try:
        with _ledger_errors():
            result = LifecycleLedger(survey.root).validate()
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("ledger", exc), status="refused")
        return
    check.evidence = {
        "version": result.get("version"),
        "generation": result.get("generation"),
    }


def read_batch(survey: Survey) -> None:
    from harness.orchestration.ledger.ledger_ops import _load_batch
    from harness.orchestration.workflow.history import _validate_batch_integrity

    check = survey.checks["batch"]
    try:
        batch = _load_batch(survey.root, survey.batch_id)
        _validate_batch_integrity(survey.root, batch)
    except HarnessError as exc:
        check.add(RecoveryDiagnostic.from_error("batch", exc), status="refused")
        check.evidence = _batch_row(survey)
        if check.evidence["present"]:
            survey.hold_reason = hold_reason_of(exc)
            check.evidence["hold_reason"] = survey.hold_reason
        return
    survey.batch = batch
    check.evidence = {
        "state": batch["state"],
        "next_action": batch.get("next_action"),
    }


def _batch_row(survey: Survey) -> JsonObject:
    """What the store holds for the batch, when the strict read refuses it."""
    try:
        row, revision = _read_store_record(survey.root, f"batches/{survey.batch_id}.json")
    except HarnessError as exc:
        return {"present": None, "error": sanitize_detail(exc.message)}
    if row is None:
        return {"present": False}
    state = row.get("state")
    return {
        "present": True,
        "revision": revision,
        "state": state if isinstance(state, str) else None,
    }


_UNKNOWN_VALUE = re.compile(r"\binvalid \w+ value '")
_MISSING_VALUE = re.compile(
    r"\binvalid \w+ value None\b|\bmissing\b|\bincomplete\b|\brequires?\b"
)


def hold_reason_of(exc: HarnessError) -> str:
    """The hold reason of a strict-read refusal of the batch record: a value the registry does
    not list, a value that is absent, or a record that does not read at all."""
    if _UNKNOWN_VALUE.search(exc.message):
        return "unknown-value"
    if _MISSING_VALUE.search(exc.message):
        return "missing-value"
    return "unreadable-record"
