"""Worker steps read from the project's ledger records and worker logs.

The records are read without the ledger lock, which a coordinator command can hold for minutes,
like the decisions list does; the log is opened for reading and stat'ed only. Nothing is written.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import LifecycleLedger
from harness.orchestration.worker_observation import (
    checkpoint_view,
    dispatch_checkpoint_ids,
    external_log_path,
    read_plain_steps,
    read_structured_steps,
    structured_log_path,
    supervised_log_path,
    unavailable_page,
)

from ..domain.worker_steps import WorkerFacts, valid_dispatch_id


def read_worker_facts(repo: Path, dispatch_id: str) -> WorkerFacts | None:
    if not valid_dispatch_id(dispatch_id):
        return None
    root = LifecycleLedger(repo / STATE_REL).records_root_lenient()
    if root is None:
        return None
    dispatch = LifecycleLedger.read_record_lenient(
        root / "dispatches" / f"{dispatch_id}.json"
    )
    if dispatch is None or dispatch.get("dispatch_id") != dispatch_id:
        return None
    status = LifecycleLedger.read_record_lenient(
        root / "dispatch-status" / f"{dispatch_id}.json"
    )
    return WorkerFacts(dispatch_id=dispatch_id, dispatch=dispatch, status=status)


def read_worker_checkpoints(repo: Path, facts: WorkerFacts) -> list[Mapping[str, object]]:
    batch_id = facts.dispatch.get("batch_id")
    root = LifecycleLedger(repo / STATE_REL).records_root_lenient()
    if root is None or not isinstance(batch_id, str) or not valid_dispatch_id(batch_id):
        return []
    batch = LifecycleLedger.read_record_lenient(root / "batches" / f"{batch_id}.json")
    found: list[Mapping[str, object]] = []
    for checkpoint_id in dispatch_checkpoint_ids(batch or {}, facts.dispatch_id):
        record = (
            LifecycleLedger.read_record_lenient(
                root / "checkpoints" / f"{checkpoint_id}.json"
            )
            if valid_dispatch_id(checkpoint_id)
            else None
        )
        if record is not None:
            found.append(checkpoint_view(record))
    return found


def read_worker_log(
    repo: Path, facts: WorkerFacts, source: str, offset: int, budget: int
) -> Mapping[str, object]:
    if source == "structured" and facts.dispatch.get("execution"):
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
