"""A batch closed by abandon or by not-required closes the status record of each open dispatch in
the runtime store too, as it did in the file ledger (#814: found by the clean-room on the store).

Both commands asked ``Path.exists`` whether the status record was there; in the store epoch the
record has no file, so the status stayed ``dispatched`` beside a batch that says otherwise.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from .runtime_store_support import Store, store_records

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the seam tests drive a Unix-socket runtime"
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    opened = Store(tmp_path)
    yield opened
    opened.stop_runtime()


def _status(store: Store) -> str:
    record = store_records(store.repo, store.runtime, store.status_path)[store.status_path]
    return str(record["state"])


def test_abandon_closes_the_status_record_of_an_open_dispatch(store: Store) -> None:
    assert _status(store) in {"dispatched", "working"}

    done = store.run(
        "batch",
        "abandon",
        "--batch",
        store.batch,
        "--approved-by",
        "operator",
        "--approved-at",
        "2026-11-13T09:00:00Z",
        "--reason",
        "the worker died",
    )

    assert done.returncode == 0, done.stderr
    assert _status(store) == "abandoned"


def test_not_required_cancels_the_status_record_of_an_open_dispatch(store: Store) -> None:
    done = store.run(
        "batch",
        "not-required",
        "--batch",
        store.batch,
        "--approved-by",
        "operator",
        "--approved-at",
        "2026-11-13T09:00:00Z",
        "--reason",
        "the change is already on the base",
    )

    assert done.returncode == 0, done.stderr
    assert _status(store) == "cancelled"
