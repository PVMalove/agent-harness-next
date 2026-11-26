"""``dispatch status`` without a filter answers when a whole collection would not fit one frame
(#1276).

The runtime refuses a ``state.read`` answer larger than one frame. A store with a long batch
history holds more dispatch records than one frame carries, so reading the whole collection failed
with ``AnswerTooLarge`` and the coordinator route could not start.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from harness.orchestration.core import state_view
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.ledger import ledger_ops
from harness.orchestration.workflow import delivery

from .runtime_store_support import Store

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the seam tests drive a Unix-socket runtime"
)

TOO_LARGE = {"dispatch-status", "dispatches"}


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store(tmp_path)
    yield opened
    opened.stop_runtime()


class _RefusingRead(ledger_ops._SnapshotRead):
    """The runtime read, refusing an unfiltered read of ``TOO_LARGE`` as an oversized frame."""

    def __call__(
        self,
        collections: Sequence[str],
        paths: Sequence[str],
        revision: int | None,
        filter_: state_view.Filter | None = None,
        /,
    ) -> tuple[dict[str, JsonObject], int | None, dict[str, int]]:
        if filter_ is None and TOO_LARGE.intersection(collections):
            raise state_view.AnswerTooLarge("the answer would not fit one frame")
        return super().__call__(collections, paths, revision, filter_)


def test_status_without_a_filter_answers_when_a_whole_collection_is_too_large(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in store.runtime.environ.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(ledger_ops, "_runtime_fetch", _RefusingRead)
    args = argparse.Namespace(
        repo=str(store.repo), state_dir=None, dispatch=None, batch=None, stale_after=None
    )

    status = delivery.dispatch_status(args)

    assert [entry["dispatch_id"] for entry in status["dispatches"]] == [store.dispatch]
    assert status["dispatches"][0]["batch_id"] == store.batch


class _RefusingEveryRead(ledger_ops._SnapshotRead):
    """The runtime read, refusing every read of the status collections, filtered or not, as an
    oversized frame."""

    def __call__(
        self,
        collections: Sequence[str],
        paths: Sequence[str],
        revision: int | None,
        filter_: state_view.Filter | None = None,
        /,
    ) -> tuple[dict[str, JsonObject], int | None, dict[str, int]]:
        if {*TOO_LARGE, "batches"}.intersection(collections):
            raise state_view.AnswerTooLarge("the answer would not fit one frame")
        return super().__call__(collections, paths, revision, filter_)


def test_status_that_cannot_fit_one_frame_is_a_coordinator_error_with_a_remedy(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in store.runtime.environ.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(ledger_ops, "_runtime_fetch", _RefusingEveryRead)
    args = argparse.Namespace(
        repo=str(store.repo), state_dir=None, dispatch=None, batch=None, stale_after=None
    )

    with pytest.raises(CoordinatorError) as raised:
        delivery.dispatch_status(args)

    assert "frame" in str(raised.value)
    assert raised.value.remedy
