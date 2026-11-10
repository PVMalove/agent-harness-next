"""Findings of the full ``/implement`` route (issue #1015) on the real coordinator and runtime.

Every case cuts a coordinator state over to the runtime store, serves it with ``harness-runtime
serve`` and drives the coordinator CLI against it, as a coordinator session does.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.orchestration.runtime_store_support import APPROVAL, Store

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the runtime store is served over a Unix socket here",
)
APPROVED = (
    "--approved-by",
    APPROVAL["approved_by"],
    "--approved-at",
    APPROVAL["approved_at"],
)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    found = Store(tmp_path)
    try:
        yield found
    finally:
        found.stop_runtime()


def _ok(result: subprocess.CompletedProcess[str]) -> JsonObject:
    assert result.returncode == 0, result.stderr
    answer: JsonObject = json.loads(result.stdout)
    return answer


def _audit_decisions(store: Store) -> list[JsonObject]:
    """The ``decision`` detail of every transition audit record of the batch, oldest first."""
    connection = sqlite3.connect(store.database, timeout=10)
    try:
        rows = connection.execute(
            "SELECT details_json FROM audit WHERE action = 'transition' ORDER BY seq"
        ).fetchall()
    finally:
        connection.close()
    found: list[JsonObject] = []
    for (text,) in rows:
        details = json.loads(text)
        if details.get("path") == store.batch_path and isinstance(
            details.get("decision"), dict
        ):
            found.append(details["decision"])
    return found


def test_an_abandoned_batch_names_who_closed_it_and_why(store: Store) -> None:
    _ok(
        store.run(
            "batch",
            "abandon",
            "--batch",
            store.batch,
            *APPROVED,
            "--reason",
            "the worker died before its report",
        )
    )

    decision = _audit_decisions(store)[-1]
    assert decision["decision"] == "abandon"
    assert decision["approver"] == {"kind": "human", "name": APPROVAL["approved_by"]}
    assert decision["approved_at"] == APPROVAL["approved_at"]
    assert decision["reason"] == "the worker died before its report"
    assert decision["open_dispatches"] == [store.dispatch]

    listed = _ok(store.run("batch", "list"))["batches"]
    assert isinstance(listed, list)
    (entry,) = [item for item in listed if item["batch_id"] == store.batch]
    assert entry["state"] == "abandoned"
    assert entry["abandoned"] == {
        "approved_by": APPROVAL["approved_by"],
        "approved_at": APPROVAL["approved_at"],
        "abandoned_at": entry["abandoned"]["abandoned_at"],
        "reason": "the worker died before its report",
    }
    assert isinstance(entry["abandoned"]["abandoned_at"], str)


def test_an_open_batch_lists_no_abandonment(store: Store) -> None:
    listed = _ok(store.run("batch", "list"))["batches"]
    assert isinstance(listed, list)
    (entry,) = [item for item in listed if item["batch_id"] == store.batch]
    assert entry["abandoned"] is None
