"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from rich.text import Text

from harness.console import brand
from harness.console.logtext import colorize_diff, colorize_log, colorize_overview


def _styles(text: Text) -> dict[str, str]:
    return {text.plain[span.start : span.end]: str(span.style) for span in text.spans}


def test_log_colours_statuses_counters_exit_codes_and_commands() -> None:
    log = colorize_log(
        "$ harness update /x\n"
        "код выхода: 1\n"
        "Итого: ok=42 warn=0 fail=2 skipped=11\n"
        "Требует исправления: 2 — см. «Как исправить»\n"
        "[FAIL] files.lock: нет\n"
        "Traceback (most recent call last):"
    )
    styles = _styles(log)
    colors = brand.STATUS_COLORS
    assert log.plain.count("\n") == 5
    assert colors["fail"] in styles["1"] and "bold" in styles["1"]
    assert colors["ok"] in styles["ok=42"]
    assert brand.PALETTE["muted"] in styles["warn=0"]
    assert colors["fail"] in styles["fail=2"]
    assert colors["fail"] in styles["[FAIL]"]
    assert colors["fail"] in styles["Traceback (most recent call last):"]


def test_a_zero_exit_code_is_green_and_the_text_is_unchanged() -> None:
    text = "код выхода: 0\nготово"
    log = colorize_log(text)
    assert log.plain == text
    assert brand.STATUS_COLORS["ok"] in _styles(log)["0"]


def test_diff_colours_additions_removals_and_hunks() -> None:
    diff = colorize_diff("--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n same")
    styles = _styles(diff)
    assert brand.STATUS_COLORS["fail"] in styles["-old"]
    assert brand.STATUS_COLORS["ok"] in styles["+new"]
    assert brand.PALETTE["secondary"] in styles["@@ -1 +1 @@"]
    assert diff.plain.endswith(" same")


def test_overview_keys_are_accented() -> None:
    overview = colorize_overview("Скилов: 32\nбез двоеточия")
    assert brand.PALETTE["primary"] in _styles(overview)["Скилов:"]
    assert overview.plain == "Скилов: 32\nбез двоеточия"
