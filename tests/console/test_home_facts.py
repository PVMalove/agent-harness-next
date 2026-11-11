"""Home context facts read from the project without the ledger lock or a runtime call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.console.backend.infrastructure.home_facts import (
    recent_sessions,
    runtime_reason,
    store_facts,
)
from harness.console.kernel.i18n_strings import EN
from harness.console.kernel.home_snapshot import RecentSession, RouteStep, StoreFacts
from harness.console.kernel.reports import BatchSummary, LedgerView, StageEntry
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.runtime_client import RUNTIME_ERROR_CODES, RuntimeClientError


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


def test_runtime_store_reads_generation_cutover_and_the_runtime_audit_count(tmp_path: Path) -> None:
    state = _pointer(tmp_path, {"version": 4, "generation": "generation-ff01", "selected_at": "t"})
    (state / "AUTHORITY.json").write_text(
        json.dumps({"cutover_at": "2026-11-05T10:00:00Z", "store_id": "s", "snapshot": "x"}),
        encoding="utf-8",
    )
    calls: list[tuple[str, object]] = []

    def runtime(operation: str, payload: dict[str, object]) -> dict[str, object]:
        calls.append((operation, payload))
        return {"audit_records": 11462, "valid": True}

    facts = store_facts(tmp_path, runtime=runtime)
    assert facts == StoreFacts(
        "runtime-store", 4, "generation-ff01", 11462, cutover_at="2026-11-05T10:00:00Z", reason=""
    )
    assert calls == [("state.validate", {"full": False})]


def test_an_unanswering_runtime_leaves_the_audit_count_unread_with_its_reason(
    tmp_path: Path,
) -> None:
    _pointer(tmp_path, {"version": 4, "generation": "generation-ff01"})

    def runtime(operation: str, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeClientError(
            "runtime_unavailable", "no runtime", remedy="start it", domain="transport"
        )

    facts = store_facts(tmp_path, runtime=runtime)
    assert facts.audit_records is None
    assert facts.generation == "generation-ff01"
    assert facts.cutover_at is None
    assert "runtime_unavailable" in facts.reason


def test_the_file_ledger_never_asks_the_runtime(tmp_path: Path) -> None:
    _pointer(tmp_path, {"version": 3, "generation": "generation-ab12"})

    def runtime(operation: str, payload: dict[str, object]) -> dict[str, object]:
        raise AssertionError("the file ledger is read from disk")

    assert store_facts(tmp_path, runtime=runtime).cutover_at is None


def test_harness_install_names_the_capabilities_and_those_outside_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.backend.infrastructure import home_facts
    from harness.console.kernel.harness_facts import HarnessState

    state = HarnessState(
        installed=True,
        installed_version="2.0.0",
        capabilities=("pvmalove-suite", "backend-orchestration"),
        skills=30,
        managed_files=200,
        updated_at="",
        orchestration=True,
    )
    monkeypatch.setattr(home_facts, "harness_state", lambda repo: state)
    install = home_facts.harness_install(tmp_path)
    assert install.capabilities == 2
    assert install.capability_names == ("pvmalove-suite", "backend-orchestration")
    assert install.uncatalogued == ("pvmalove-suite",)


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
        updated_at="2026-11-03T02",
    )
    assert sessions[1].route == ()
    assert sessions[0].updated_at == "2026-11-03T02"
    assert sessions[1].updated_at == "2026-11-02"


@pytest.mark.parametrize(
    "error",
    [
        *(
            RuntimeClientError(code, "refused", remedy="see the log", domain="transport")
            for code in RUNTIME_ERROR_CODES
        ),
        ConnectionResetError("reset"),
        OSError("socket"),
        ValueError("not json"),
    ],
)
def test_every_runtime_reason_has_an_english_catalog_entry(error: Exception) -> None:
    reason = runtime_reason(error)
    assert reason.startswith("runtime не отвечает (")
    assert reason in EN, reason


def test_an_unknown_error_type_is_never_named_raw_in_the_reason() -> None:
    assert runtime_reason(ConnectionResetError("reset")) == runtime_reason(OSError("io"))
    assert "Error" not in runtime_reason(ValueError("bad"))


def test_a_runtime_without_an_audit_count_has_an_english_reason(tmp_path: Path) -> None:
    _pointer(tmp_path, {"version": 4, "generation": "generation-ff01"})
    facts = store_facts(tmp_path, runtime=lambda operation, payload: {"valid": True})
    assert facts.audit_records is None
    assert facts.reason in EN
