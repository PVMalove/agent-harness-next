"""The «Обновить Harness» snapshot: its wire codec, the update diff paths the server serves and the
facts it collects without running `harness diff` for a project the harness is not installed in."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.console.backend import composition
from harness.console.backend.infrastructure import screen_facts
from harness.console.kernel import data as console_data
from harness.console.kernel.harness_facts import HarnessState
from harness.console.kernel.home_snapshot import StoreFacts
from harness.console.kernel.update_harness_snapshot import (
    UpdateHarnessFacts,
    diff_paths,
)

STATE = HarnessState(True, "1.0.0", ("engineering-suite",), 3, 7, "t", True)
DRIFT: dict[str, object] = {
    "state": "drift",
    "conflict": ["AGENTS.md"],
    "package_changed": ["harness/a.py", "AGENTS.md"],
    "seed_differing": [".harness/project.json"],
    "local_changed": 2,
}


def test_the_facts_round_trip_through_their_payload() -> None:
    sut = UpdateHarnessFacts(STATE, "1.0.1", DRIFT)

    assert UpdateHarnessFacts.from_payload(sut.to_payload()) == sut
    bare = UpdateHarnessFacts(HarnessState(False, "", (), 0, 0, "", False), "1.0.1", None)
    assert UpdateHarnessFacts.from_payload(bare.to_payload()) == bare


STORE = StoreFacts("file-ledger", 3, "generation-1", 12)


def test_the_store_facts_and_the_target_schema_round_trip_through_their_payload() -> None:
    sut = UpdateHarnessFacts(STATE, "1.0.1", DRIFT, store=STORE, store_target_schema=4)

    payload = sut.to_payload()

    assert payload["store_target_schema"] == 4
    assert payload["store"] == {
        "authority": "file-ledger",
        "schema": 3,
        "generation": "generation-1",
        "audit_records": 12,
        "cutover_at": None,
        "reason": "",
        "start_command": "",
    }
    assert UpdateHarnessFacts.from_payload(payload) == sut


@pytest.mark.parametrize(
    "change",
    [
        {"store": {}},
        {"store": {"authority": "file-ledger"}},
        {"store_target_schema": "4"},
        {"store_target_schema": True},
    ],
)
def test_store_fields_off_the_schema_are_a_value_error(change: dict[str, object]) -> None:
    payload = {**UpdateHarnessFacts(STATE, "1", None, STORE, 4).to_payload(), **change}

    with pytest.raises(ValueError):
        UpdateHarnessFacts.from_payload(payload)


def test_the_facts_carry_the_store_and_the_ledger_version_the_update_migrates_to(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.orchestration.ledger.lifecycle import STORE_LEDGER_VERSION

    monkeypatch.setattr(screen_facts, "store_facts", lambda repo: STORE)

    found = UpdateHarnessFacts.from_payload(screen_facts.update_harness_facts(tmp_path))

    assert found.store == STORE
    assert found.store_target_schema == STORE_LEDGER_VERSION


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {"state": STATE.to_payload(), "package_version": "1"},
        {"state": STATE.to_payload(), "package_version": 1, "drift": None},
        {"state": STATE.to_payload(), "package_version": "1", "drift": []},
        {"state": {}, "package_version": "1", "drift": None},
        {"state": STATE.to_payload(), "package_version": "1", "drift": None, "x": 1},
    ],
)
def test_a_payload_off_the_schema_is_a_value_error(payload: object) -> None:
    with pytest.raises(ValueError):
        UpdateHarnessFacts.from_payload(payload)


def test_the_diff_paths_are_every_listed_file_of_the_drift() -> None:
    assert diff_paths(DRIFT) == frozenset(
        {"AGENTS.md", "harness/a.py", ".harness/project.json"}
    )
    assert diff_paths(None) == frozenset()
    assert diff_paths({"added": [1, "x"], "retired": "y"}) == frozenset({"x"})


def test_the_facts_of_a_project_without_the_harness_never_run_harness_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def drift(repo: Path) -> object:
        raise AssertionError("harness diff ran")

    monkeypatch.setattr(console_data, "drift_report", drift)

    found = UpdateHarnessFacts.from_payload(screen_facts.update_harness_facts(tmp_path))

    assert found.state.installed is False and found.drift is None
    assert found.package_version


def test_the_facts_of_an_installed_project_carry_its_drift_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(screen_facts, "harness_state", lambda repo: STATE)
    monkeypatch.setattr(console_data, "drift_report", lambda repo: DRIFT)

    found = UpdateHarnessFacts.from_payload(screen_facts.update_harness_facts(tmp_path))

    assert (found.state, found.drift) == (STATE, DRIFT)
    service = composition.screen_service(tmp_path)
    assert service._collect_update_harness is screen_facts.update_harness_facts
    assert service._read_update_diff is screen_facts.update_diff
