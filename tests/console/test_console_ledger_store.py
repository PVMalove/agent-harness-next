"""The console ledger view in the runtime-store epoch: the records come from `state.read`."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from harness.console.kernel import reports
from harness.console.kernel.dispatch_containers import container_payload
from harness.console.kernel.reports import StoreUnreadable, load_ledger_view
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import STORE_LEDGER_VERSION, JsonObject


def _store_epoch(repo: Path) -> None:
    state = repo / STATE_REL
    state.mkdir(parents=True)
    (state / "ledger.json").write_text(
        json.dumps({"version": STORE_LEDGER_VERSION}), encoding="utf-8"
    )


class FakeStore:
    """`state.read` over records by path: a collection answers its directory, a path itself."""

    def __init__(self, records: Mapping[str, JsonObject]) -> None:
        self.records = dict(records)
        self.calls: list[tuple[list[str], list[str]]] = []

    def __call__(
        self, collections: Sequence[str], paths: Sequence[str]
    ) -> Mapping[str, object]:
        self.calls.append((list(collections), list(paths)))
        return {
            path: record
            for path, record in self.records.items()
            if path in paths or path.split("/", 1)[0] in collections
        }


def _batch(batch_id: str, *dispatch_ids: str) -> JsonObject:
    return {
        "batch_id": batch_id,
        "ticket": "#1183",
        "state": "active",
        "created_at": "2026-11-16T09:00:00+00:00",
        "branch": "feature/issue-1183-x",
        "dispatches": [
            {"dispatch_id": dispatch_id, "role": "qa", "state": "approved"}
            for dispatch_id in dispatch_ids
        ],
    }


def test_a_dispatch_created_after_the_cutover_is_read_from_the_store(
    tmp_path: Path,
) -> None:
    _store_epoch(tmp_path)
    store = FakeStore(
        {
            "batches/b-new.json": _batch("b-new", "d-new"),
            "dispatches/d-new.json": {
                "dispatch_id": "d-new",
                "batch_id": "b-new",
                "role": "qa",
                "created_at": "2026-11-16T09:05:00+00:00",
                "qa_execution": {"supervisor": "harness-runtime"},
                "runtime_access": {"container": {"engine": "docker"}},
                "runtime_images": {"proxy": None, "worker": "sha256:aa"},
            },
            "dispatch-status/d-new.json": {
                "dispatch_id": "d-new",
                "state": "reported",
                "heartbeat_at": "2026-11-16T09:06:00+00:00",
            },
            "reports/d-new.json": {
                "dispatch_id": "d-new",
                "ticket": "#1183",
                "role": "qa",
                "outcome": "completed",
                "output": "ok",
            },
            "audit/audit-chain-000000000001.json": {
                "at": "2026-11-16T09:30:00+00:00",
                "action": "immutable-record",
                "details": {"path": "reports/d-new.json"},
            },
            "qa-lane/attempts/a-1.json": {
                "dispatch_id": "d-new",
                "stage": "lint",
                "failed_at": "2026-11-16T09:04:00+00:00",
                "message": "lint failed",
            },
            "qa-lane/lease.json": {"owner_id": "x"},
        }
    )

    view = load_ledger_view(tmp_path, store_read=store)

    assert view.unavailable is None
    assert [batch.batch_id for batch in view.batches] == ["b-new"]
    assert [(entry.dispatch_id, entry.batch_id, entry.reported_at) for entry in view.reports] == [
        ("d-new", "b-new", "2026-11-16T09:30:00+00:00")
    ]
    assert [(stage.dispatch_id, stage.state) for stage in view.stages] == [
        ("d-new", "reported")
    ]
    assert [attempt.message for attempt in view.qa_attempts] == ["lint failed"]
    # The store answers no QA gate log, so the view has no QA runs rather than stale ones.
    assert view.qa_runs == []
    assert container_payload(view)["containers"] == [
        {
            "dispatch_id": "d-new",
            "batch_id": "b-new",
            "ticket": "#1183",
            "role": "qa",
            "kind": "qa",
            "engine": "docker",
            "image": "sha256:aa",
            "stage_state": "reported",
            "state": "stopped",
        }
    ]


def test_each_store_read_stays_small_enough_for_one_frame(tmp_path: Path) -> None:
    _store_epoch(tmp_path)
    ids = [f"d-{index:03}" for index in range(reports.STORE_PATH_CHUNK + 1)]
    records: dict[str, JsonObject] = {"batches/b-1.json": _batch("b-1", *ids)}
    for dispatch_id in ids:
        records[f"dispatches/{dispatch_id}.json"] = {
            "dispatch_id": dispatch_id,
            "batch_id": "b-1",
            "role": "qa",
        }
    store = FakeStore(records)

    view = load_ledger_view(tmp_path, store_read=store)

    assert len(view.dispatch_records()) == len(ids)
    # A collection is read on its own, and dispatches and reports by path, chunk by chunk.
    assert all(len(collections) <= 1 for collections, _ in store.calls)
    assert not any(
        name in {"dispatches", "reports"} for collections, _ in store.calls for name in collections
    )
    assert max(len(paths) for _, paths in store.calls) == reports.STORE_PATH_CHUNK


def test_an_unanswered_store_read_makes_the_view_unavailable(tmp_path: Path) -> None:
    _store_epoch(tmp_path)

    def down(collections: Sequence[str], paths: Sequence[str]) -> Mapping[str, object]:
        raise StoreUnreadable("runtime store не ответил на state.read (runtime_unavailable)")

    view = load_ledger_view(tmp_path, store_read=down)

    assert view.unavailable == "runtime store не ответил на state.read (runtime_unavailable)"
    assert view.batches == [] and view.reports == []
