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
from typing import cast

import pytest

from harness.json_types import JsonObject
from tests.orchestration.runtime_store_support import APPROVAL, Store, store_records

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


def test_the_architect_brief_names_the_scope_of_its_batch(store: Store) -> None:
    path = f"dispatches/{store.dispatch}.json"
    brief = store_records(store.repo, store.runtime, path)[path]
    batch = store_records(store.repo, store.runtime, store.batch_path)[store.batch_path]

    assert brief["role"] == "architect"
    assert brief["write_paths"] == []
    assert brief["allowed_paths"] == batch["allowed_paths"]
    assert _ok(store.run("ledger", "validate"))["valid"] is True


def _plan_entry(paths: list[str], covers: list[int]) -> JsonObject:
    return {
        "id": "first",
        "summary": "read the store",
        "expected_paths": paths,
        "covers": covers,
    }


def _report_with_plan(store: Store, plan: list[JsonObject]) -> str:
    """The architect's completion report, carrying ``plan`` as its commit_plan."""
    path = store.report_file()
    report = json.loads(path.read_text(encoding="utf-8"))
    report["commit_plan"] = plan
    path.write_text(json.dumps(report), encoding="utf-8")
    return str(path)


def _dispatch_state(store: Store) -> str:
    path = f"dispatch-status/{store.dispatch}.json"
    state = store_records(store.repo, store.runtime, path)[path]["state"]
    assert isinstance(state, str)
    return state


@pytest.fixture
def scoped(tmp_path: Path) -> Iterator[Store]:
    found = Store(tmp_path, allowed_paths=("services/**",))
    try:
        yield found
    finally:
        found.stop_runtime()


def test_report_submit_refuses_a_commit_plan_outside_the_batch_scope(
    scoped: Store,
) -> None:
    refused = scoped.run(
        "report",
        "submit",
        "--file",
        _report_with_plan(scoped, [_plan_entry(["docs/x.md"], [1])]),
    )

    assert refused.returncode != 0
    assert "docs/x.md" in refused.stderr
    assert "services/**" in refused.stderr
    assert "risks" in refused.stderr
    assert _dispatch_state(scoped) == "working"


def test_report_submit_refuses_a_commit_plan_that_names_an_unknown_item(
    scoped: Store,
) -> None:
    refused = scoped.run(
        "report",
        "submit",
        "--file",
        _report_with_plan(scoped, [_plan_entry(["services/x.py"], [2])]),
    )

    assert refused.returncode != 0
    assert "covers unknown definition-of-done items [2]" in refused.stderr
    assert _dispatch_state(scoped) == "working"


def test_an_accept_pins_the_commit_plan_of_the_architect_report(
    scoped: Store,
) -> None:
    plan = [_plan_entry(["services/x.py"], [1])]
    _ok(scoped.run("report", "submit", "--file", _report_with_plan(scoped, plan)))

    _ok(
        scoped.run(
            "batch",
            "decide",
            "--batch",
            scoped.batch,
            "--decision",
            "accept",
            *APPROVED,
        )
    )

    batch = store_records(scoped.repo, scoped.runtime, scoped.batch_path)[
        scoped.batch_path
    ]
    assert batch["commit_plan"] == plan
    dispatches = cast(list[JsonObject], batch["dispatches"])
    decision = cast(JsonObject, dispatches[0]["decision"])
    assert isinstance(decision["commit_plan_sha256"], str)
    developer = _developer_brief(scoped)
    assert developer["commit_plan"] == plan
    assert developer["allowed_paths"] == developer["write_paths"] == ["services/**"]


DEVELOPER = (
    "--role",
    "developer",
    "--runtime",
    "claude",
    "--purpose",
    "work",
    "--model",
    "sonnet",
    "--effort",
    "high",
)


def _developer_brief(store: Store) -> JsonObject:
    proposal = _ok(store.run("dispatch", "propose", "--batch", store.batch, *DEVELOPER))
    created = _ok(
        store.run(
            "dispatch",
            "create",
            "--batch",
            store.batch,
            *DEVELOPER,
            "--transition-digest",
            str(proposal["transition_digest"]),
            *APPROVED,
        )
    )
    return cast(JsonObject, created["brief"])


def test_the_developer_brief_carries_the_accepted_architect_design(
    store: Store,
) -> None:
    report = store.report_file()
    output = json.loads(report.read_text(encoding="utf-8"))["output"]
    _ok(store.run("report", "submit", "--file", str(report)))
    _ok(
        store.run(
            "batch", "decide", "--batch", store.batch, "--decision", "accept", *APPROVED
        )
    )
    batch = store_records(store.repo, store.runtime, store.batch_path)[store.batch_path]
    (architect,) = cast(list[JsonObject], batch["dispatches"])

    brief = _developer_brief(store)

    assert brief["accepted_design"] == {
        "dispatch_id": store.dispatch,
        "report_sha256": architect["report_sha256"],
        "output": output,
    }
    path = f"dispatches/{store.dispatch}.json"
    assert (
        store_records(store.repo, store.runtime, path)[path]["accepted_design"] is None
    )
    assert _ok(store.run("ledger", "validate"))["valid"] is True
