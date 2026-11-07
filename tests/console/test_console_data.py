"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.console.kernel import data as console_data


def test_harness_version_reads_the_package_version_file() -> None:
    """Проверить, что версия харнесса считывается из файла версии пакета."""
    assert (
        console_data.harness_version()
        == console_data.VERSION_FILE.read_text(encoding="utf-8").strip()
    )
    assert console_data.harness_version()


def test_dashboard_aggregates_supplied_health_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.health.model import CheckResult, Report

    memory = CheckResult("memory.index", "memory", "warn", "rebuild index")
    report = Report(
        1,
        str(tmp_path),
        False,
        [
            CheckResult("files.lock", "files", "ok", "ready"),
            memory,
            CheckResult("files.agents", "files", "fail", "missing"),
            CheckResult("repo_map.tier", "repo_map", "skipped", "minimal"),
        ],
    )
    monkeypatch.setattr(console_data, "run_health", lambda repo, **kwargs: report)
    monkeypatch.setattr(console_data, "harness_version", lambda: "1.2.3")
    monkeypatch.setattr(console_data, "drift_state", lambda repo: "clean")
    monkeypatch.setattr(console_data, "active_batches", lambda repo: 2)

    result = console_data.collect_dashboard(tmp_path)

    assert (result.ok, result.warn, result.fail, result.skipped) == (1, 1, 1, 1)
    assert (result.repo_map_tier, result.harness_version, result.active_batches) == (
        "minimal",
        "1.2.3",
        2,
    )
    assert result.memory_index is memory
    assert result.problems == (
        ("fail", "files.agents", "missing"),
        ("warn", "memory.index", "rebuild index"),
    )
