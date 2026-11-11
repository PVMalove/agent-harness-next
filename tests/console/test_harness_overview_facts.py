"""The Harness overview facts: drift file count, state store, runtime adapters and the container
engine inventory."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.console.backend.infrastructure import screen_facts
from harness.console.kernel import data as console_data


CONTAINERS: dict[str, object] = {"engine": "docker", "info_problem": "fake"}


@pytest.fixture(autouse=True)
def no_engine_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """The container engine inventory runs processes: these tests replace it."""
    monkeypatch.setattr(screen_facts, "container_facts", lambda repo: CONTAINERS)


def test_drift_files_count_every_differing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        console_data,
        "drift_report",
        lambda repo: {"state": "drift", "added": ["a"], "package_changed": ["b", "c"]},
    )
    facts = screen_facts.harness_facts(tmp_path)
    assert (facts["drift"], facts["drift_files"]) == ("drift", 3)
    assert facts["store"] == {
        "authority": "none",
        "schema": None,
        "generation": None,
        "audit_records": None,
        "cutover_at": None,
        "reason": "",
    }
    # No lock: the adapter set is unknown, never "current".
    assert facts["adapters"] is None
    assert facts["containers"] is CONTAINERS


def test_unreadable_drift_is_unknown_with_a_null_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_data, "drift_report", lambda repo: None)
    facts = screen_facts.harness_facts(tmp_path)
    assert (facts["drift"], facts["drift_files"]) == ("unknown", None)


def test_adapters_of_the_installed_capabilities_carry_their_status() -> None:
    repo = Path(__file__).parents[2]
    adapters = screen_facts.adapter_facts(repo)
    if adapters is None:
        pytest.skip("the repository has no installed harness lock")
    assert all(
        set(item) == {"path", "status", "problem"}
        and item["status"] in {"current", "outdated", "missing"}
        for item in adapters
    )
