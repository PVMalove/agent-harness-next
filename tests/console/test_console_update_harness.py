"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.kernel.catalog import seed_update_entry
from harness.console.tui import stats as console_stats
from harness.console.tui.screens.update_harness import (
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


def test_each_mode_is_its_server_job_and_the_seed_mode_names_the_ticked_files() -> None:
    import pytest

    from harness.console.kernel.catalog import UPDATE_SEED_SELECTED
    from harness.console.tui.screens.update_harness import (
        TOO_MANY_SEEDS,
        update_job,
    )

    entry, values = update_job("update-force-managed", [])
    assert (entry.key, values) == ("update-force-managed", {})
    entry, values = update_job("update-seed-selected", ["a.md", "b/c.md"])
    assert entry is UPDATE_SEED_SELECTED and values == {"paths": "a.md\nb/c.md"}
    with pytest.raises(ValueError, match="update-force-seed|всех seed") as refused:
        update_job("update-seed-selected", [f"dir/{'я' * 40}-{n}.md" for n in range(30)])
    assert str(refused.value) == TOO_MANY_SEEDS


def test_the_update_screen_reads_the_snapshot_and_updates_through_the_server() -> None:
    """The screen neither runs `harness diff` nor reads a diff or the lock itself, and starts no
    process: the snapshot, the diff and the update come from the console server client."""
    import ast

    from harness.console.tui.screens import update_harness

    tree = ast.parse(Path(str(update_harness.__file__)).read_text(encoding="utf-8"))
    names = {
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Attribute, ast.Name))
    }

    local = {
        "drift_report",
        "harness_state",
        "update_diff_text",
        "capturing_runner",
        "process_argv",
        "harness_version",
    }
    assert not local & names
    assert {"update_harness", "update_diff", "ServerJobRunner"} <= names
