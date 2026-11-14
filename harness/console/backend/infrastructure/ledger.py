"""Pending human decisions read from the project's ledger.

In the runtime-store epoch one Rust IPC read supplies the records; legacy installations read JSON
without the ledger lock, which a coordinator command can hold for minutes. A listed decision can
therefore be stale: the console never decides from it. Each item names commands executed through
``job.start`` with prefilled ``values``; the coordinator and the runtime recheck the live state
(the transition digest, the batch state, the request digest) when the command runs.

Kinds: ``batch-approval`` (a planned batch), ``dispatch-approval`` (a batch awaiting approval with
nothing else open: ``dispatch-propose`` shows the transition, ``dispatch-create`` approves it),
``report-decision`` (a completion report without a coordinator decision), ``attention`` (a batch
that needs attention) and ``native-permission`` (a request a live worker's runtime staged).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from harness.orchestration.core.constants import LIVE_DISPATCH_STATES, STATE_REL
from harness.orchestration.ledger.lifecycle import (
    JsonObject,
    LifecycleLedger,
    store_is_authority,
)
from harness.orchestration.ledger.recovery_chain import active_dispatches
from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError

from ...kernel.coordinator_catalog import COORDINATOR_COMMANDS
from ...kernel.json_fields import text
from ..domain.approvals import (
    DecisionItem,
    DecisionsSnapshot,
    batch_items,
    bounded_decisions,
    native_permission_item,
)
from .native_permission import NATIVE_PERMISSION_COMMANDS

_REVERSIBILITY = {
    **{entry.key: entry.reversibility.value for entry in COORDINATOR_COMMANDS},
    **{entry.key: entry.reversibility.value for entry in NATIVE_PERMISSION_COMMANDS},
}
_NATIVE_COMMANDS = [entry.key for entry in NATIVE_PERMISSION_COMMANDS]
_COLLECTIONS = ("batches", "reports", "dispatches", "dispatch-status")


def _records(root: Path, directory: str) -> list[JsonObject]:
    records: list[JsonObject] = []
    for path in sorted((root / directory).glob("*.json")):
        record = LifecycleLedger.read_record_lenient(path)
        if record is not None:
            records.append(record)
    return records


def _active(batch: Mapping[str, object]) -> list[JsonObject]:
    return active_dispatches(cast(JsonObject, batch))


def _native_items(
    repo: Path,
    statuses: Sequence[JsonObject],
    batches: dict[str, JsonObject],
    dispatches: dict[str, JsonObject],
) -> list[DecisionItem]:
    from harness.orchestration.runtime_permissions import pending_requests

    live = {state.value for state in LIVE_DISPATCH_STATES}
    items: list[DecisionItem] = []
    for status in statuses:
        dispatch = dispatches.get(text(status.get("dispatch_id")))
        if (
            dispatch is None
            or status.get("state") not in live
            or not isinstance(status.get("adapter_receipt"), dict)
        ):
            continue
        batch = batches.get(text(dispatch.get("batch_id")), {})
        batch = {**batch, "batch_id": text(dispatch.get("batch_id"))}
        try:
            requests = pending_requests(repo, dispatch, status)
        except ValueError:
            continue  # the receipt points outside the project's worker log storage
        for request in requests:
            items.append(
                native_permission_item(
                    batch, dispatch, request, _NATIVE_COMMANDS, _REVERSIBILITY
                )
            )
    return items


def collect_decisions(repo: Path) -> DecisionsSnapshot:
    """The project's pending decisions, at most ``MAX_DECISIONS``; ``total`` counts them all."""
    state = repo / STATE_REL
    if store_is_authority(state):
        # One authoritative read of all four collections: never open runtime.db in Python or
        # fall back to the archived file generation, even when the runtime cannot answer.
        try:
            reply = RuntimeClient(repo).call(
                "state.read",
                operation_id=f"console.decisions-{uuid.uuid4().hex}",
                payload={"collections": list(_COLLECTIONS), "paths": []},
                timeout_seconds=2,
            )
        except RuntimeClientError as exc:
            return DecisionsSnapshot(unavailable=True, error_code=exc.code)
        raw = reply.result.get("records")
        if not isinstance(raw, dict):
            return DecisionsSnapshot(unavailable=True, error_code="invalid_response")
        collections = {
            directory: [
                record
                for path, record in raw.items()
                if path.startswith(f"{directory}/") and isinstance(record, dict)
            ]
            for directory in _COLLECTIONS
        }
    else:
        root = LifecycleLedger(state).records_root_lenient()
        if root is None:
            return DecisionsSnapshot(unavailable=True)
        collections = {
            directory: _records(root, directory) for directory in _COLLECTIONS
        }
    batches: dict[str, JsonObject] = {}
    for record in collections["batches"]:
        batch_id = record.get("batch_id")
        if isinstance(batch_id, str) and isinstance(record.get("dispatches", []), list):
            batches[batch_id] = record
    reports = {
        text(report.get("dispatch_id")): report for report in collections["reports"]
    }
    dispatches = {
        text(record.get("dispatch_id")): record for record in collections["dispatches"]
    }
    found: list[DecisionItem] = []
    for batch in batches.values():
        try:
            found.extend(batch_items(batch, reports, _active, _REVERSIBILITY))
        except (KeyError, TypeError, AttributeError):
            continue  # a malformed record is not a decision the console can offer
    found.extend(
        _native_items(repo, collections["dispatch-status"], batches, dispatches)
    )
    return bounded_decisions(found)
