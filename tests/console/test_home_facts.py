"""Home context facts read from the project without the ledger lock or a runtime call."""

from __future__ import annotations

import json
from pathlib import Path

from harness.console.backend.infrastructure.home_facts import (
    recent_sessions,
    store_facts,
)
from harness.console.kernel.home_snapshot import RecentSession, RouteStep, StoreFacts
from harness.console.kernel.reports import BatchSummary, LedgerView, StageEntry
from harness.orchestration.core.constants import STATE_REL


def _pointer(repo: Path, payload: object) -> Path:
    state = repo / STATE_REL
    state.mkdir(parents=True)
    (state / "ledger.json").write_text(json.dumps(payload), encoding="utf-8")
    return state


def test_store_without_a_ledger_is_none(tmp_path: Path) -> None:
    assert store_facts(tmp_path) == StoreFacts("none", None, None, None)


def test_file_ledger_reports_schema_generation_and_audit_count(tmp_path: Path) -> None:
    state = _pointer(
        tmp_path,
        {"version": 3, "generation": "generation-ab12", "selected_at": "t"},
    )
    audit = state / "generations" / "generation-ab12" / "audit"
    audit.mkdir(parents=True)
    for index in range(3):
        (audit / f"{index}.json").write_text("{}", encoding="utf-8")
    assert store_facts(tmp_path) == StoreFacts("file-ledger", 3, "generation-ab12", 3)


def test_runtime_store_is_named_without_asking_the_runtime(tmp_path: Path) -> None:
    _pointer(tmp_path, {"version": 4})
    assert store_facts(tmp_path) == StoreFacts("runtime-store", 4, None, None)


def test_recent_sessions_list_the_newest_batches_with_their_route() -> None:
    view = LedgerView(
        batches=[
            BatchSummary("b-3", "#3", "active", "2026-11-03", branch="feature/c"),
            BatchSummary("b-2", "#2", "published", "2026-11-02"),
            BatchSummary("b-1", "#1", "published", "2026-11-01"),
            BatchSummary("b-0", "#0", "published", "2026-10-31"),
        ],
        stages=[
            StageEntry("d-2", "b-3", "#3", "developer", "working", "2026-11-03T02"),
            StageEntry("d-1", "b-3", "#3", "architect", "reported", "2026-11-03T01"),
        ],
    )
    sessions = recent_sessions(view)
    assert [session.batch_id for session in sessions] == ["b-3", "b-2", "b-1"]
    assert sessions[0] == RecentSession(
        "b-3",
        "#3",
        "active",
        "feature/c",
        "2026-11-03",
        (RouteStep("architect", "reported"), RouteStep("developer", "working")),
    )
    assert sessions[1].route == ()
