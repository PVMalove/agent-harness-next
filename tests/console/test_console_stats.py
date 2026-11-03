"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
from pathlib import Path

from harness.console import reports, stats


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
