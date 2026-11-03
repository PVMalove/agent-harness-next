"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console import stats as console_stats
from harness.console.catalog import seed_update_entry
from harness.console.screens.update_harness import (
    render_drift,
    render_versions,
)

PAYLOAD: dict[str, object] = {
    "state": "drift",
    "package_changed": [".harness/a.py", ".harness/b.py"],
    "added": [".harness/new.py"],
    "missing": [],
    "retired": [],
    "local_changed": [".harness/local.py"],
    "conflict": [".harness/conflict.py"],
    "seed_differing": [".claude/rules/one.md", ".claude/rules/two.md"],
}


def _state(*, installed: bool = True) -> console_stats.HarnessState:
    if not installed:
        return console_stats.HarnessState(False, "", (), 0, 0, "", False)
    return console_stats.HarnessState(
        True, "1.3.2", ("backend-orchestration",), 32, 219, "2026-10-11 11:00 UTC", True
    )


def test_versions_and_drift_are_rendered_with_counters() -> None:
    versions = render_versions(_state(), "1.4.0")
    assert "1.3.2" in versions.plain and "1.4.0" in versions.plain
    assert "Доступно обновление" in versions.plain
    assert "Версия актуальна" in render_versions(_state(), "1.3.2").plain
    assert "не установлен" in render_versions(_state(installed=False), "1.4.0").plain
    drift = render_drift(PAYLOAD)
    assert "обновятся" in drift.plain and "в конфликте" in drift.plain
    assert "Расхождений нет" in render_drift({"state": "clean"}).plain
    assert "Not installed" not in render_drift(None, language="en").plain
    assert "Could not check drift" in render_drift(None, language="en").plain


def test_seed_update_entry_builds_one_flag_per_file(tmp_path: Path) -> None:
    entry = seed_update_entry(["a.md", "b/c.md"])
    assert entry.cli_argv(tmp_path) == [
        "harness",
        "update",
        str(tmp_path),
        "--force-seed-file",
        "a.md",
        "--force-seed-file",
        "b/c.md",
    ]
    assert entry.needs_confirmation


def test_counters_and_file_tags_carry_symbols() -> None:
    drift = render_drift(PAYLOAD).plain.splitlines()
    assert drift == [
        "   2 ✔ обновятся",
        "   1 ✔ добавятся",
        "   1 ⚠ с локальными правками (сохранятся)",
        "   1 ✖ в конфликте (нужна перезапись)",
    ]
    narrow = render_drift(PAYLOAD, narrow=True).plain.splitlines()
    assert narrow[-2:] == ["   1 ⚠ ваши правки сохранятся", "   1 ✖ конфликт"]
    assert (
        render_drift(PAYLOAD, language="en").plain.splitlines()[0]
        == "   2 ✔ will be updated"
    )


def test_the_versions_verdict_is_a_symbol_and_a_word() -> None:
    current = render_versions(_state(), "1.3.2").plain
    assert "✔ Версия актуальна" in current
    assert "Состав" in current and "Скилов" in current and "Lock обновлён" in current
    assert "⚠ Доступно обновление" in render_versions(_state(), "1.4.0").plain
    narrow = render_versions(_state(), "1.3.2", narrow=True).plain
    assert "Установлено" in narrow and "Состав" in narrow and "Скилов" not in narrow
    missing = render_versions(_state(installed=False), "1.4.0").plain.splitlines()
    assert missing == [
        "✖ Харнесс не установлен: нет читаемого .harness/harness.lock",
        "Установите его через «Открыть проект».",
    ]
