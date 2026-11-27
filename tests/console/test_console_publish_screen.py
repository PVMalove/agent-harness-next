"""The Publish screen words its preflight checks and the PR state from the ledger facts."""

from __future__ import annotations

from harness.console.kernel.reports import BatchSummary, ReportEntry, StageEntry
from harness.console.tui.screens.publish import _check, _pr_value


def _stage(outcome: str | None) -> StageEntry:
    report = (
        ReportEntry("d-qa", "b-1", "#1", "qa", outcome, "", {})
        if outcome is not None
        else None
    )
    return StageEntry("d-qa", "b-1", "#1", "qa", "reported", "", report)


def test_a_preflight_check_passes_only_on_a_completed_report() -> None:
    assert _check(_stage("completed")) == "ok"
    assert _check(_stage("failed")) == "fail"
    assert _check(_stage("blocked")) == "fail"
    assert _check(_stage(None)) == "warn"
    assert _check(None) == "warn"


def test_the_pr_is_its_link_or_its_state_in_words() -> None:
    linked = BatchSummary(
        "b-1",
        "#1",
        "completed",
        "",
        pr_url="https://example.com/pull/1",
        pr_state="found",
    )
    missing = BatchSummary("b-2", "#2", "active", "", pr_state="missing")

    assert _pr_value(linked, "ru").plain == "https://example.com/pull/1"
    assert _pr_value(missing, "ru").plain == "PR не создан"
    assert _pr_value(missing, "en").plain == "PR not created"
    assert _pr_value(missing, "ru", named=False).plain == "не создан"
