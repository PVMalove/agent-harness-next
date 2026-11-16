"""The dispatch containers of the Orchestration screen, projected from the ledger records."""

from __future__ import annotations

import pytest

from harness.json_types import JsonObject
from harness.console.kernel.dispatch_containers import container_payload
from harness.console.kernel.reports import LedgerView, StageEntry

EXECUTION: JsonObject = {"supervisor": "harness-runtime", "timeout_seconds": 3600}
QA_EXECUTION: JsonObject = {"supervisor": "harness-runtime", "command_timeout_seconds": 900}


def _view(*items: tuple[str, JsonObject, str, str]) -> LedgerView:
    """A view of dispatch records with their stage state and last heartbeat."""
    view = LedgerView()
    for dispatch_id, record, state, heartbeat in items:
        view._dispatches[dispatch_id] = record
        view.stages.append(
            StageEntry(
                dispatch_id,
                text(record, "batch_id"),
                text(record, "ticket"),
                text(record, "role"),
                state,
                "2026-11-16T10:00:00Z",
                heartbeat_at=heartbeat,
            )
        )
    return view


def text(record: JsonObject, key: str) -> str:
    value = record.get(key)
    return value if isinstance(value, str) else ""


def _record(role: str, **extra: JsonObject) -> JsonObject:
    return {"batch_id": "batch-1", "ticket": "#7", "role": role, **extra}


def test_an_empty_ledger_has_no_containers() -> None:
    assert container_payload(LedgerView()) == {"containers": [], "counts": {}}


def test_a_dispatch_without_an_execution_section_is_not_a_container() -> None:
    view = _view(("d-1", _record("developer"), "working", "2026-11-16T10:01:00Z"))
    assert container_payload(view) == {"containers": [], "counts": {}}


def test_worker_and_qa_containers_carry_their_facts() -> None:
    view = _view(
        (
            "d-1",
            _record(
                "developer",
                execution={**EXECUTION, "engine": "docker"},
                runtime_images={"worker": "sha256:aa", "proxy": "sha256:bb"},
            ),
            "working",
            "2026-11-16T10:01:00Z",
        ),
        ("d-2", _record("qa", qa_execution=QA_EXECUTION), "reported", ""),
    )
    assert container_payload(view) == {
        "containers": [
            {
                "dispatch_id": "d-1",
                "batch_id": "batch-1",
                "ticket": "#7",
                "role": "developer",
                "kind": "worker",
                "engine": "docker",
                "image": "sha256:aa",
                "stage_state": "working",
                "state": "running",
            },
            {
                "dispatch_id": "d-2",
                "batch_id": "batch-1",
                "ticket": "#7",
                "role": "qa",
                "kind": "qa",
                "engine": "",
                "image": "",
                "stage_state": "reported",
                "state": "stopped",
            },
        ],
        "counts": {"running": 1, "stopped": 1},
    }


@pytest.mark.parametrize(
    ("stage_state", "heartbeat", "expected"),
    [
        ("dispatched", "", "running"),
        ("working", "2026-11-16T10:01:00Z", "running"),
        ("reported", "2026-11-16T10:01:00Z", "stopped"),
        ("checkpointed", "", "stopped"),
        ("blocked", "", "not-created"),
        ("failed", "", "not-created"),
        ("cancelled", "", "not-created"),
        ("blocked", "2026-11-16T10:01:00Z", "stopped"),
        ("failed", "2026-11-16T10:01:00Z", "stopped"),
        ("approved", "", "unknown"),
        ("неизвестно", "", "unknown"),
    ],
)
def test_the_container_state_comes_from_the_stage_state(
    stage_state: str, heartbeat: str, expected: str
) -> None:
    view = _view(("d-1", _record("developer", execution=EXECUTION), stage_state, heartbeat))
    payload = container_payload(view)
    containers = payload["containers"]
    assert isinstance(containers, list)
    assert [item["state"] for item in containers] == [expected]
    assert payload["counts"] == {expected: 1}
