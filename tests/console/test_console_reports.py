"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from harness.console.kernel import reports
from harness.console.kernel.reports import (
    BatchSummary,
    ReportEntry,
    StageEntry,
    batch_status,
    load_ledger_view,
    outcome_status,
    report_section_lines,
    stage_status,
)
from harness.orchestration.ledger.lifecycle import JsonObject


def test_stage_filters_combine_and_sort_unknown_times_last() -> None:
    from harness.console.kernel.reports import ReportEntry, StageEntry, select_stages

    report = ReportEntry(
        "dispatch-old",
        "batch-a",
        "#10",
        "developer",
        "completed",
        "2026-10-12T09:00:00Z",
        {},
    )
    stages = [
        StageEntry(
            "dispatch-unknown", "batch-b", "#20", "qa", "неизвестно", "bad date"
        ),
        StageEntry(
            "dispatch-live",
            "batch-a",
            "#10",
            "developer",
            "working",
            "2026-10-12T12:00:00+02:00",
        ),
        StageEntry(
            "dispatch-old",
            "batch-a",
            "#10",
            "developer",
            "reported",
            report.reported_at,
            report,
        ),
        StageEntry(
            "dispatch-tie",
            "batch-c",
            "#30",
            "architect",
            "dispatched",
            "2026-10-12T10:00:00Z",
        ),
    ]
    assert [entry.dispatch_id for entry in select_stages(stages)] == [
        "dispatch-live",
        "dispatch-tie",
        "dispatch-old",
        "dispatch-unknown",
    ]
    assert [entry.dispatch_id for entry in select_stages(stages, descending=False)] == [
        "dispatch-old",
        "dispatch-live",
        "dispatch-tie",
        "dispatch-unknown",
    ]
    assert [
        entry.dispatch_id
        for entry in select_stages(
            stages,
            ticket="10",
            role="Developer",
            state="working",
            completion="open",
            date="2026-10-12",
        )
    ] == ["dispatch-live"]
    assert [
        entry.dispatch_id
        for entry in select_stages(stages, outcome="completed", completion="finished")
    ] == ["dispatch-old"]
    assert select_stages(stages, state="working", outcome="completed") == []
    assert [
        entry.dispatch_id
        for entry in select_stages(stages, sort_by="role", descending=False)
    ] == ["dispatch-tie", "dispatch-live", "dispatch-old", "dispatch-unknown"]
    assert [
        entry.dispatch_id
        for entry in select_stages(stages, sort_by="state", descending=False)
    ] == ["dispatch-tie", "dispatch-old", "dispatch-live", "dispatch-unknown"]


def test_missing_ledger_is_reported_as_unavailable(tmp_path: Path) -> None:
    view = load_ledger_view(tmp_path)
    assert view.unavailable is not None
    assert view.reports == []
    assert view.batches == []


def _stage(state: str, outcome: str | None) -> StageEntry:
    report = (
        ReportEntry("dispatch-x", "batch-x", "#1", "developer", outcome, "", {})
        if outcome is not None
        else None
    )
    return StageEntry("dispatch-x", "batch-x", "#1", "developer", state, "", report)


def test_stage_status_is_a_symbol_and_a_label_for_every_known_outcome() -> None:
    cases = {
        ("reported", "completed"): "✔ отчёт получен · завершено",
        ("reported", "blocked"): "⚠ отчёт получен · заблокировано",
        ("reported", "failed"): "✖ отчёт получен · ошибка",
        ("working", None): "⚠ в работе · отчёта ещё нет",
    }
    for (state, outcome), shown in cases.items():
        assert stage_status(_stage(state, outcome)).render("ru") == shown


def test_stage_status_is_shorter_on_a_narrow_terminal_and_follows_the_language() -> (
    None
):
    entry = _stage("reported", "completed")
    assert stage_status(entry, narrow=True).render("ru") == "✔ отчёт · завершено"
    assert stage_status(entry).render("en") == "✔ report received · completed"


def test_stage_status_shows_an_unknown_ledger_value_as_it_is() -> None:
    assert (
        stage_status(_stage("reported", "weird")).render("ru")
        == "⚠ отчёт получен · weird"
    )
    assert (
        stage_status(_stage("queued", None)).render("ru") == "⚠ queued · отчёта ещё нет"
    )


def test_batch_status_names_the_state_with_a_symbol_and_keeps_an_unknown_one() -> None:
    def batch(state: str) -> BatchSummary:
        return BatchSummary("batch-x", "#1", state, "")

    assert batch_status(batch("completed")).render("ru") == "✔ завершён"
    assert batch_status(batch("blocked")).render("ru") == "⚠ заблокирован"
    assert batch_status(batch("active")).render("en") == "▶ in progress"
    assert batch_status(batch("mystery")).render("ru") == "⚠ mystery"


def test_outcome_status_keeps_the_ledger_word_beside_its_symbol() -> None:
    assert outcome_status("completed").render("ru") == "✔ completed"
    assert outcome_status("blocked").render("ru") == "⚠ blocked"
    assert outcome_status("failed").render("ru") == "✖ failed"
    assert outcome_status("odd").render("ru") == "⚠ odd"


def test_report_review_axis_verdict_follows_the_recorded_severity_not_the_findings_count() -> (
    None
):
    info: JsonObject = {"severity": "info", "summary": "заметка", "evidence": "a.py:1"}
    review: JsonObject = {
        "candidate_commit": "c" * 40,
        "standards": {"severity": "clean", "findings": [info]},
        "spec": {"severity": "warning", "findings": []},
    }
    lines = dict(report_section_lines({"review": review}))["Review"]
    axes = {
        text.split(" · ")[0]: status.render("ru")
        for status, text in lines
        if status is not None
    }
    assert axes == {"standards": "✔ clean", "spec": "⚠ warning"}

    for severity, shown in (
        ("none", "✔ none"),
        ("clean", "✔ clean"),
        ("warning", "⚠ warning"),
        ("blocker", "✖ blocker"),
    ):
        single: JsonObject = {"standards": {"severity": severity, "findings": []}}
        [(status, text)] = dict(report_section_lines({"review": single}))["Review"][1:]
        assert status is not None and status.render("ru") == shown
        assert text == "standards · находок: 0"


def test_filters_combine_without_loading_a_ledger() -> None:
    from harness.console.kernel.reports import filter_reports

    reports = [
        ReportEntry("a", "batch", "#101", "developer", "completed", "2026-01-02", {}),
        ReportEntry("b", "batch", "#101", "qa", "blocked", "2026-01-03", {}),
        ReportEntry("c", "other", "#202", "developer", "blocked", "", {}),
    ]
    assert filter_reports(reports, ticket="101", role="Developer") == [reports[0]]
    assert filter_reports(reports, outcome="blocked", date="2026-01") == [reports[1]]
    assert filter_reports(reports, date="1999") == []
    assert filter_reports(reports) == reports


def _codec_view() -> reports.LedgerView:
    report = reports.ReportEntry(
        dispatch_id="d-1",
        batch_id="b-1",
        ticket="#1",
        role="developer",
        outcome="completed",
        reported_at="2026-01-01T00:00:00+00:00",
        report={"output": "body", "checks_run": []},
    )
    view = reports.LedgerView(
        reports=[report],
        batches=[
            reports.BatchSummary("b-1", "#1", "active", "2026-01-01", "feature/x", pr_url="u")
        ],
        qa_runs=[
            reports.QaRun(
                artifact="qa-artifacts/a.log",
                logged_at="t",
                dispatch_id=None,
                ticket="?",
                outcome="нет отчёта",
                commands=[("make lint", 0), ("pytest", 1)],
                tail=["a", "b"],
                total_lines=2,
            )
        ],
        qa_attempts=[reports.QaAttempt("d-2", "run", "t", "boom")],
        unavailable=None,
        _dispatches={
            "d-1": {"dispatch_id": "d-1", "role": "developer", "secret": "x"},
            "d-2": {"dispatch_id": "d-2"},
        },
        _batch_records={"b-1": {"batch_id": "b-1"}},
    )
    view.stages.extend(
        [
            reports.StageEntry("d-1", "b-1", "#1", "developer", "reported", "t", report),
            reports.StageEntry("d-2", "b-1", "#1", "qa", "working", "t"),
        ]
    )
    return view


def test_the_ledger_payload_round_trips_without_report_bodies_or_raw_records() -> None:
    view = _codec_view()
    payload = reports.ledger_payload(view)
    text_form = json.dumps(payload)
    assert "body" not in text_form and "secret" not in text_form
    back = reports.ledger_from_payload(json.loads(text_form))
    bodiless = replace(view.reports[0], report={})
    assert back.reports == [bodiless]
    assert back.batches == view.batches
    assert back.qa_runs == view.qa_runs and back.qa_attempts == view.qa_attempts
    assert back.stages == [replace(view.stages[0], report=bodiless), view.stages[1]]
    assert back.unavailable is None
    assert sorted(back.dispatch_records(), key=str) == sorted(
        [{"role": "developer"}, {}], key=str
    )
    assert back.timeline("b-1") is None


def test_a_malformed_ledger_payload_is_refused() -> None:
    payload = reports.ledger_payload(_codec_view())
    broken: object
    for broken in (
        [],
        {**payload, "extra": 1},
        {**payload, "version": 99},
        {**payload, "batches": [{"batch_id": 1}]},
        {**payload, "stages": [{**payload["stages"][0], "report": "nope"}]},  # type: ignore[index]
        {**payload, "qa_runs": [{**payload["qa_runs"][0], "commands": [["x"]]}]},  # type: ignore[index]
        {**payload, "dispatches": {"d": {"role": 1}}},
    ):
        with pytest.raises(ValueError):
            reports.ledger_from_payload(broken)


def test_the_timeline_payload_round_trips_and_refuses_a_broken_one() -> None:
    timeline = reports.BatchTimeline(
        batch=reports.BatchSummary("b-1", "#1", "active", "t"),
        role_flow=["developer", "qa"],
        events=[
            reports.TimelineEvent("t1", "state", "active"),
            reports.TimelineEvent("t2", "dispatch", "d-1", role="developer"),
        ],
    )
    payload = json.loads(json.dumps(reports.timeline_payload(timeline)))
    assert reports.timeline_from_payload(payload) == timeline
    with pytest.raises(ValueError):
        reports.timeline_from_payload({**payload, "events": [{"at": "t"}]})
