"""The durable intent of a recovery action: written before it runs, finished after it."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from harness.errors import HarnessError
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _now
from harness.orchestration.ledger.ledger_ops import (
    _ledger_errors,
    _ledger_lock,
    _read_store_record,
    read_state,
    store_is_authority,
)
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.operational_hold import FILE_EPOCH_REMEDY, sanitize_detail
from harness.orchestration.recovery.model import (
    ACTIONS,
    INTENT_STATUSES,
    RecoveryInternalError,
    RecoveryInterrupted,
)
from harness.orchestration.recovery.runtime import runtime_hello, runtime_problems

INTENT_CONTRACT = "recoveryIntent.v1"
INTENT_DIRECTORY = "recovery/intent"


def intent_relative(batch_id: str) -> str:
    """The path of the recovery intent of ``batch_id`` in the store."""
    return f"{INTENT_DIRECTORY}/{batch_id}.json"


def _write_intent(repo: Path, root: Path, record: JsonObject, *, own: str | None) -> None:
    """Write ``record`` as the intent of its batch in a store unit of its own.

    ``own`` is the correlation ID a finish expects to find: an intent another action wrote since
    is never overwritten by this one."""
    batch_id = str(record["batch_id"])
    ledger = LifecycleLedger(root)
    with _ledger_lock(ledger):
        stored, _ = _read_store_record(root, intent_relative(batch_id))
        if own is not None and (stored is None or stored.get("correlation_id") != own):
            return
        path = ledger.records_root() / intent_relative(batch_id)
        with _ledger_errors():
            if stored is None:
                ledger.write_immutable(path, record)
            else:
                ledger.replace(path, record)


@dataclass
class Intent:
    """The durable record of one action: written before it runs, finished after it."""

    repo: Path
    root: Path
    record: JsonObject

    def finish(self, status: str, outcome: str | None, detail: str | None) -> None:
        if status not in INTENT_STATUSES:
            raise ValueError(f"unknown recovery intent status {status!r}")
        self.record.update(
            {
                "status": status,
                "outcome": outcome,
                "detail": None if detail is None else sanitize_detail(detail),
                "updated_at": _now(),
            }
        )
        _write_intent(
            self.repo, self.root, self.record, own=str(self.record["correlation_id"])
        )


def _require_recovery_store(repo: Path, root: Path, batch_id: str) -> None:
    """An action that writes an intent needs the runtime-store epoch, a runtime that keeps the
    recovery records and the batch's row in the store."""
    if not store_is_authority(root):
        raise CoordinatorError(
            "recovery runs on the runtime store; this repository is in the file-ledger epoch",
            remedy=FILE_EPOCH_REMEDY,
        )
    problems = runtime_problems(runtime_hello(repo))
    if problems:
        raise CoordinatorError(
            f"the runtime cannot keep the recovery records: {'; '.join(problems)}",
            remedy="update harness-runtime to the version of this harness and restart it "
            "with 'harness-runtime serve', then repeat the command",
        )
    with read_state(LifecycleLedger(root), repo):
        batch, _ = _read_store_record(root, f"batches/{batch_id}.json")
    if batch is None:
        raise CoordinatorError(
            f"the runtime store holds no batch {batch_id}",
            remedy="name a batch that 'coordinator.py batch status' lists",
        )


@contextmanager
def tracked(repo: Path, root: Path, batch_id: str, action: str) -> Iterator[Intent]:
    """Record the intent of ``action`` as pending, run it and record how it ended.

    A refusal ends ``refused``; cancel, end of input or an interrupt ends ``interrupted`` and is
    raised as a refusal; any other exception ends ``refused`` as an internal error with a
    correlation ID.  The caller finishes a normal run with its outcome.  Each write of the intent
    is a store unit of its own, so it is kept whatever the action does next."""
    if action not in ACTIONS:
        raise ValueError(f"unknown recovery action {action!r}")
    _require_recovery_store(repo, root, batch_id)
    moment = _now()
    intent = Intent(
        repo,
        root,
        {
            "contract": INTENT_CONTRACT,
            "batch_id": batch_id,
            "action": action,
            "status": "pending",
            "outcome": None,
            "detail": None,
            "requested_at": moment,
            "updated_at": moment,
            "correlation_id": str(uuid.uuid4()),
        },
    )
    _write_intent(repo, root, intent.record, own=None)
    try:
        yield intent
    except (KeyboardInterrupt, EOFError, asyncio.CancelledError) as exc:
        intent.finish("interrupted", None, type(exc).__name__)
        raise RecoveryInterrupted(
            f"recovery {action} was interrupted; its intent is recorded",
            remedy=f"run 'coordinator.py recovery status --batch {batch_id}' and repeat "
            f"'recovery {action}': every completed step is kept and nothing is repeated",
        ) from exc
    except HarnessError as exc:
        intent.finish("refused", "refused", exc.message)
        raise
    except Exception as exc:  # noqa: BLE001 -- recorded and raised as an internal invariant
        error = RecoveryInternalError(action, exc, intent.record["correlation_id"])
        intent.finish("refused", "refused", error.message)
        raise error from exc
    if intent.record["status"] == "pending":
        intent.finish("done", "done", None)


def read_intent(root: Path, batch_id: str) -> JsonObject | None:
    """The persisted intent a restarted console shows; an unreadable one is shown as such."""
    record, _ = _read_store_record(root, intent_relative(batch_id))
    if record is None:
        return None
    if record.get("contract") != INTENT_CONTRACT or record.get("batch_id") != batch_id:
        return {"contract": INTENT_CONTRACT, "unreadable": "integrity-failure"}
    return record
