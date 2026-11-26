"""Worker steps read from the project's ledger records and worker logs.

The records are read without the ledger lock, which a coordinator command can hold for minutes,
like the decisions list does; the log is opened for reading and stat'ed only. Nothing is written.
In the runtime-store epoch (ADR 0020) the records come from the store, never from the archived
file generation; a store that does not answer is ``WorkerLedgerUnavailable``.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import LifecycleLedger, store_is_authority
from harness.orchestration.runtime_client import (
    RuntimeClient,
    RuntimeClientError,
    read_state,
)
from harness.orchestration.worker_observation import (
    checkpoint_view,
    dispatch_checkpoint_ids,
    external_log_path,
    qa_commands_dir,
    read_plain_steps,
    read_qa_stage_steps,
    read_structured_steps,
    structured_log_path,
    supervised_log_path,
    unavailable_page,
)

from ..application.ports import WorkerLedgerUnavailable
from ...kernel.execution_facts import ExecutionSummary, observe_execution
from ..domain.worker_steps import WorkerFacts, valid_dispatch_id

# A short read: a page of steps is asked for every second.
STORE_READ_SECONDS = 2


def _records(repo: Path, paths: Sequence[str]) -> dict[str, Mapping[str, object]]:
    """The ledger records at ``paths`` (``<collection>/<id>.json``) that exist and are objects."""
    state = repo / STATE_REL
    if store_is_authority(state):
        try:
            raw = read_state(
                RuntimeClient(repo),
                {"collections": [], "paths": list(paths)},
                operation_id=f"console.worker-steps-{uuid.uuid4().hex}",
                timeout_seconds=STORE_READ_SECONDS,
            ).records
        except RuntimeClientError as exc:
            raise WorkerLedgerUnavailable(f"{exc.code}: {exc.message}") from None
        return {
            path: record
            for path, record in raw.items()
            if path in paths and isinstance(record, dict)
        }
    root = LifecycleLedger(state).records_root_lenient()
    if root is None:
        return {}
    found: dict[str, Mapping[str, object]] = {}
    for path in paths:
        record = LifecycleLedger.read_record_lenient(root / path)
        if record is not None:
            found[path] = record
    return found


def read_worker_facts(repo: Path, dispatch_id: str) -> WorkerFacts | None:
    if not valid_dispatch_id(dispatch_id):
        return None
    dispatch_path = f"dispatches/{dispatch_id}.json"
    status_path = f"dispatch-status/{dispatch_id}.json"
    records = _records(repo, [dispatch_path, status_path])
    dispatch = records.get(dispatch_path)
    if dispatch is None or dispatch.get("dispatch_id") != dispatch_id:
        return None
    return WorkerFacts(
        dispatch_id=dispatch_id, dispatch=dispatch, status=records.get(status_path)
    )


def read_worker_checkpoints(repo: Path, facts: WorkerFacts) -> list[Mapping[str, object]]:
    batch_id = facts.dispatch.get("batch_id")
    if not isinstance(batch_id, str) or not valid_dispatch_id(batch_id):
        return []
    batch_path = f"batches/{batch_id}.json"
    batch = _records(repo, [batch_path]).get(batch_path)
    paths = [
        f"checkpoints/{checkpoint_id}.json"
        for checkpoint_id in dispatch_checkpoint_ids(batch or {}, facts.dispatch_id)
        if valid_dispatch_id(checkpoint_id)
    ]
    records = _records(repo, paths) if paths else {}
    return [checkpoint_view(records[path]) for path in paths if path in records]


def read_worker_log(
    repo: Path, facts: WorkerFacts, source: str, offset: int, budget: int
) -> Mapping[str, object]:
    reader: Callable[[Path, int, int], Mapping[str, object]]
    if source == "stages":
        path, reason = qa_commands_dir(repo / STATE_REL, facts.dispatch, facts.status)
        reader = read_qa_stage_steps
    elif source == "structured" and facts.dispatch.get("execution"):
        path, reason = supervised_log_path(repo / STATE_REL, facts.dispatch)
        reader = read_structured_steps
    elif source == "structured":
        receipt = facts.status.get("adapter_receipt") if facts.status else None
        path, reason = structured_log_path(repo, receipt, facts.dispatch_id)
        reader = read_structured_steps
    else:
        path, reason = external_log_path(repo, facts.dispatch)
        reader = read_plain_steps
    if path is None:
        return unavailable_page(source, reason or "no_log", offset)
    return reader(path, offset, budget)



def read_execution_summary(repo: Path, facts: WorkerFacts) -> ExecutionSummary | None:
    """What the runtime observes of the execution of a supervised worker or a container QA run
    (#1296); None for an unsupervised dispatch, on the file ledger or when the runtime does not
    answer. Only the runtime is asked; the ledger is not written."""
    if not (facts.dispatch.get("execution") or facts.dispatch.get("qa_execution")):
        return None
    return observe_execution(repo, facts.dispatch_id)
