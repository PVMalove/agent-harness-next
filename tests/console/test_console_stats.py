"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
from pathlib import Path

from harness.console.kernel import reports
from harness.console.tui import stats


def test_empty_and_missing_ledgers_are_explained(tmp_path: Path) -> None:
    view = reports.load_ledger_view(tmp_path)
    assert view.unavailable
    assert view.unavailable in stats.usage_text(view)
    assert "не запускался" in stats.pipeline_stats_text(
        stats.pipeline_stats(reports.LedgerView())
    )


def test_harness_state_reads_the_lock_and_skills(tmp_path: Path) -> None:
    assert stats.harness_state_text(stats.harness_state(tmp_path), "1.0.0").startswith(
        "Харнесс не установлен"
    )
    harness_dir = tmp_path / ".harness"
    (harness_dir / "skills" / "grilling").mkdir(parents=True)
    (harness_dir / "skills" / "grilling" / "SKILL.md").write_text("x", encoding="utf-8")
    (harness_dir / "skills" / "notes").mkdir()
    (harness_dir / "harness.lock").write_text(
        json.dumps(
            {
                "package_version": "0.9.0",
                "capabilities": ["engineering-suite"],
                "files": {"a": "1", "b": "2"},
            }
        ),
        encoding="utf-8",
    )

    state = stats.harness_state(tmp_path)
    text = stats.harness_state_text(state, "1.0.0")

    assert (state.skills, state.managed_files, state.orchestration) == (1, 2, False)
    assert "0.9.0 (версия пакета харнесса: 1.0.0)" in text
    assert "Capability: engineering-suite" in text
    assert "Оркестрация: не подключена" in text


def test_short_time_keeps_minutes_only() -> None:
    assert stats.short_time("2026-09-28T09:52:05.4+00:00") == "2026-09-28 09:52"
    assert stats.short_time("") == ""
    assert stats.short_time("вчера") == "вчера"


def test_pipeline_stats_are_the_same_through_the_substituted_client() -> None:
    from ._home_client import FakeHomeClient
    from ._screen_facts import ledger

    view = ledger()
    served = FakeHomeClient(Path("."), load_ledger=lambda repo: view).reports()
    assert stats.pipeline_stats(served) == stats.pipeline_stats(view)
    assert stats.batches_in_state(served, stats.ALL_STATES) == stats.batches_in_state(
        view, stats.ALL_STATES
    )


def test_the_harness_state_survives_its_json_payload(tmp_path: Path) -> None:
    import pytest

    from harness.console.kernel.harness_facts import HarnessState

    state = HarnessState(True, "0.9.0", ("engineering-suite",), 3, 7, "2026", True)
    assert stats.HarnessState is HarnessState
    assert HarnessState.from_payload(json.loads(json.dumps(state.to_payload()))) == state
    broken: object
    for broken in ({**state.to_payload(), "skills": "3"}, {"installed": True}, []):
        with pytest.raises(ValueError):
            HarnessState.from_payload(broken)


def test_the_pipeline_usage_counts_are_the_numbers_of_the_tui_usage_line(
    tmp_path: Path,
) -> None:
    import re

    from harness.console.kernel import pipeline_stats
    from ._screen_facts import ledger

    view = ledger()
    usage = pipeline_stats.pipeline_usage(view)
    numbers = [int(found) for found in re.findall(r"\d+", stats.usage_text(view))]
    assert numbers == [
        usage["batches"], usage["tickets"], usage["dispatches"], usage["reports"]
    ]
    assert usage["unavailable"] is None
    assert stats.pipeline_stats is pipeline_stats.pipeline_stats
    assert stats.PipelineStats is pipeline_stats.PipelineStats

    missing = reports.load_ledger_view(tmp_path)
    assert pipeline_stats.pipeline_usage(missing) == {
        "unavailable": missing.unavailable,
        "batches": 0,
        "tickets": 0,
        "dispatches": 0,
        "reports": 0,
    }
