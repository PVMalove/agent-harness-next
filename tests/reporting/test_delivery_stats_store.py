"""Delivery stats read the orchestration ledger of the runtime-store epoch too (#814).

Release 2.0.0 keeps operational state only in the runtime store; the metrics come from the same
records, read through ``state.read`` of the runtime that serves the repository.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from harness.reporting.delivery_stats import orchestration_metrics, ticket_of_branch
from tests.orchestration.runtime_store_support import STATE_REL, Store, store_records

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the seam tests drive a Unix-socket runtime"
)


def test_the_metrics_of_a_ticket_come_from_the_runtime_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path)
    try:
        for key, value in store.runtime.environ.items():
            monkeypatch.setenv(key, value)
        # The generations of the file ledger stay after the cutover as the import source; the
        # metrics must not read them, so the test removes them.
        shutil.rmtree(store.repo / STATE_REL / "generations")
        batch = store_records(store.repo, store.runtime, store.batch_path)[store.batch_path]
        number = ticket_of_branch(batch["branch"])
        assert number is not None

        metrics = orchestration_metrics(store.repo, {number})

        assert metrics["status"] == "ok", metrics
        assert str(number) in metrics["tickets"]
    finally:
        store.stop_runtime()


def test_a_store_without_its_runtime_names_serve(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.stop_runtime()

    metrics = orchestration_metrics(store.repo, {1})

    assert metrics["status"] != "ok"
    assert "harness-runtime serve" in metrics["reason"]
