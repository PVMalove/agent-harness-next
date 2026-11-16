"""The dispatch containers of the Orchestration screen, projected from the ledger records.

A dispatch runs in a container when its approved record carries the execution the runtime
supervises (``execution``, ADR 0022) or a container QA (``qa_execution``). The state shown is
derived from the dispatch stage state in the ledger, never from runtime liveness: the console
reads only the records the ledger view already holds and calls no runtime or coordinator.
Standard library only."""

from __future__ import annotations

from collections import Counter

from ...json_types import JsonObject
from .reports import LedgerView, StageEntry

# The stage states of a dispatch whose worker is live in the ledger.
RUNNING_STATES = frozenset({"dispatched", "working"})
# The stage states of a dispatch that finished its work.
FINISHED_STATES = frozenset({"reported", "checkpointed"})
# The stage states of a stopped dispatch that may never have started a worker.
HALTED_STATES = frozenset({"blocked", "failed", "cancelled", "abandoned", "auto_stop"})


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _section(record: JsonObject, key: str) -> JsonObject | None:
    value = record.get(key)
    return value if isinstance(value, dict) else None


def _state(stage: StageEntry | None) -> str:
    """running, stopped, not-created or unknown from the stage state of the dispatch."""
    if stage is None:
        return "unknown"
    if stage.state in RUNNING_STATES:
        return "running"
    if stage.state in FINISHED_STATES:
        return "stopped"
    if stage.state in HALTED_STATES:
        # A heartbeat or a report is the only ledger evidence that a worker was launched.
        launched = bool(stage.heartbeat_at) or stage.report is not None
        return "stopped" if launched else "not-created"
    return "unknown"


def container_payload(view: LedgerView) -> dict[str, object]:
    """The containers of the ledger view with their counts by state; empty when none ran."""
    stages = {stage.dispatch_id: stage for stage in view.stages}
    containers: list[dict[str, str]] = []
    for dispatch_id, record in view._dispatches.items():
        execution = _section(record, "execution")
        qa_execution = _section(record, "qa_execution")
        if execution is None and qa_execution is None:
            continue
        images = _section(record, "runtime_images") or {}
        engine = next(
            (
                _text(section.get("engine"))
                for section in (execution, qa_execution, images)
                if section is not None and _text(section.get("engine"))
            ),
            "",
        )
        stage = stages.get(dispatch_id)
        containers.append(
            {
                "dispatch_id": dispatch_id,
                "batch_id": stage.batch_id if stage else _text(record.get("batch_id")),
                "ticket": stage.ticket if stage else _text(record.get("ticket")),
                "role": stage.role if stage else _text(record.get("role")),
                "kind": "qa" if qa_execution is not None else "worker",
                "engine": engine,
                "image": _text(images.get("worker")),
                "stage_state": stage.state if stage else "",
                "state": _state(stage),
            }
        )
    counts = Counter(item["state"] for item in containers)
    return {"containers": containers, "counts": dict(counts)}
