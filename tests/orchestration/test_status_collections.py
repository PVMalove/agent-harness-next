"""The records that ``dispatch status`` reads from the store view (#1276), without a runtime.

The runtime refuses a ``state.read`` answer larger than one frame. These tests replay that refusal
through a fake fetch, so they run where no ``harness-runtime`` binary is built.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from harness.orchestration.core import state_view
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.workflow import delivery

BATCHES = ("batch-a", "batch-b")


class _Store:
    """Two batches with one dispatch each; ``refuse`` decides which reads are too large."""

    def __init__(self, refuse: str) -> None:
        self.refuse = refuse
        self.records: dict[str, JsonObject] = {}
        for batch in BATCHES:
            dispatch = f"dispatch-{batch}"
            self.records[f"batches/{batch}.json"] = {"batch_id": batch}
            for name in ("dispatch-status", "dispatches"):
                self.records[f"{name}/{dispatch}.json"] = {
                    "batch_id": batch,
                    "dispatch_id": dispatch,
                }
        self.filters: list[tuple[str, state_view.Filter | None]] = []

    def _refused(self, collection: str, filter_: state_view.Filter | None) -> bool:
        if self.refuse == "unfiltered-dispatches":
            return filter_ is None and collection in {"dispatch-status", "dispatches"}
        if self.refuse == "batches":
            return collection == "batches"
        return False

    def fetch(
        self,
        collections: Sequence[str],
        paths: Sequence[str],
        revision: int | None,
        filter_: state_view.Filter | None = None,
    ) -> tuple[dict[str, JsonObject], int | None, dict[str, int]]:
        found: dict[str, JsonObject] = {}
        for collection in collections:
            self.filters.append((collection, filter_))
            if self._refused(collection, filter_):
                raise state_view.AnswerTooLarge("the answer would not fit one frame")
            for path, record in self.records.items():
                if path.split("/")[0] != collection:
                    continue
                if filter_ is not None and (
                    (filter_.batch_id is not None and record["batch_id"] != filter_.batch_id)
                    or (
                        filter_.dispatch_id is not None
                        and record.get("dispatch_id") != filter_.dispatch_id
                    )
                ):
                    continue
                found[path] = record
        return found, 1, {}


def _collections(
    store: _Store, tmp_path: Path, batch_id: str | None = None
) -> tuple[dict[str, JsonObject], dict[str, JsonObject], dict[str, JsonObject]]:
    view = state_view.StateView(tmp_path, store.fetch)
    return delivery._status_collections(view, batch_id, None)


def test_whole_collections_are_read_once_when_they_fit_one_frame(tmp_path: Path) -> None:
    store = _Store(refuse="none")

    statuses, dispatches, batches = _collections(store, tmp_path)

    assert len(statuses) == len(dispatches) == len(batches) == 2
    assert store.filters == [
        ("dispatch-status", None),
        ("dispatches", None),
        ("batches", None),
    ]


def test_too_large_collections_are_read_one_batch_at_a_time(tmp_path: Path) -> None:
    store = _Store(refuse="unfiltered-dispatches")

    statuses, dispatches, batches = _collections(store, tmp_path)

    assert sorted(statuses) == [
        "dispatch-status/dispatch-batch-a.json",
        "dispatch-status/dispatch-batch-b.json",
    ]
    assert sorted(dispatches) == [
        "dispatches/dispatch-batch-a.json",
        "dispatches/dispatch-batch-b.json",
    ]
    assert sorted(batches) == ["batches/batch-a.json", "batches/batch-b.json"]
    assert {
        filter_.batch_id for _name, filter_ in store.filters if filter_ is not None
    } == set(BATCHES)


def test_a_filtered_read_that_is_too_large_is_a_coordinator_error(tmp_path: Path) -> None:
    store = _Store(refuse="batches")

    with pytest.raises(CoordinatorError) as raised:
        _collections(store, tmp_path, batch_id="batch-a")

    assert "frame" in str(raised.value)
    assert "--dispatch" in raised.value.remedy


def test_batches_too_large_for_one_frame_is_a_coordinator_error(tmp_path: Path) -> None:
    store = _Store(refuse="batches")

    with pytest.raises(CoordinatorError) as raised:
        _collections(store, tmp_path)

    assert "frame" in str(raised.value)
    assert raised.value.remedy
