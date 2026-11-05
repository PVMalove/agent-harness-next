"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.tui.screens.project_setup import ProjectSetupScreen


def test_report_summary_separates_checked_skipped_and_failing_checks() -> None:
    from harness.console.tui.screens.project_setup import (
        ChecksSummary,
        summarize_report,
    )
    from harness.health.model import CheckResult, Fix, Report

    report = Report(
        1,
        "/x",
        False,
        [
            CheckResult("environment.codex_sandbox", "environment", "ok", "ok"),
            CheckResult("tracker.auth", "tracker", "skipped", "офлайн"),
            CheckResult("files.project_json", "files", "fail", "bad", Fix("fix")),
            CheckResult("files.agents_md", "files", "warn", "old"),
        ],
    )
    # A skipped check is not a success: 4 checks, 3 ran, 2 need a fix, 1 was not checked.
    assert summarize_report(report) == ChecksSummary(3, 4, 2, 1)


def test_the_busy_note_has_an_english_text() -> None:
    from harness.console.kernel import i18n

    assert (
        i18n.tr("en", "Дождитесь окончания операции")
        == "Wait for the operation to finish"
    )


def test_setup_output_marks_report_statuses_but_not_plain_list_items() -> None:
    from harness.console.tui.screens.diagnostics import styled_log

    text = "- установка\nИтого: ok=1 warn=0 fail=1 skipped=1\n[FAIL] env.uv: нет\n- net: офлайн"
    assert styled_log(text).plain.split("\n") == [
        "- установка",
        "Итого: ✔ ok=1 ⚠ warn=0 ✖ fail=1 ○ skipped=1",
        "✖ [FAIL] env.uv: нет",
        "○ - net: офлайн",
    ]


def test_styled_log_ignores_foreign_lines_that_only_look_like_a_report_total() -> None:
    from harness.console.tui.screens.diagnostics import styled_log

    text = "Итого: 3 файла\n- элемент списка"
    assert styled_log(text).plain == text


def test_open_project_has_no_escape_binding_of_its_own() -> None:
    from textual.binding import Binding

    own = ProjectSetupScreen.__dict__.get("BINDINGS", [])
    keys = [b.key if isinstance(b, Binding) else b[0] for b in own]
    assert "escape" not in keys
    assert not hasattr(ProjectSetupScreen, "action_cancel")


def test_the_screen_shows_no_demo_data_from_the_mockup() -> None:
    """The mockup's sample values (branch, counts, paths, version) are not in the sources: the
    screen shows only what the console receives."""
    root = Path(__file__).resolve().parents[2] / "harness" / "console" / "tui"
    for source in (root / "screens" / "project_setup.py", root / "project_target.py"):
        text = source.read_text(encoding="utf-8")
        for demo in (
            "feature/issue-721",
            "16 из 27",
            "11 онлайн",
            "/home/malove",
            "1.4.6",
        ):
            assert demo not in text, f"{source.name}: {demo}"


def test_an_option_button_keeps_both_lines_of_its_label() -> None:
    """Guards the private Textual API `_OptionButton` relies on (`_make_label`, `_label`)."""
    from textual.geometry import Size

    from harness.console.tui.screens.project_setup import _OptionButton

    button = _OptionButton("name\ndescription")
    assert button._label.plain == "name\ndescription"
    assert button.get_content_height(Size(40, 10), Size(80, 24), 40) == 2
