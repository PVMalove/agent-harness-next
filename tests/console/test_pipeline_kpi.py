"""The pipeline KPIs the server computes from the ledger."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from harness.json_types import JsonObject
from harness.console.kernel.pipeline_kpi import (
    EvidenceRow,
    PipelineKpi,
    ReportsKpi,
    duration_text,
    evidence_matrix,
    pipeline_analytics,
    pipeline_analytics_from_payload,
    pipeline_kpi,
    pipeline_kpi_from_payload,
    reports_kpi,
    reports_kpi_from_payload,
)
from harness.console.kernel.reports import (
    BatchSummary,
    LedgerView,
    QaRun,
    ReportEntry,
    StageEntry,
)

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def _batch(batch_id: str, state: str, created: str, pr: str = "") -> BatchSummary:
    return BatchSummary(batch_id, f"#{batch_id}", state, created, pr_created_at=pr)


def _stage(batch_id: str, role: str, at: str) -> StageEntry:
    return StageEntry(
        f"d-{batch_id}-{role}-{at}", batch_id, f"#{batch_id}", role, "working", at
    )


def _qa(ticket: str, outcome: str, at: str) -> ReportEntry:
    return ReportEntry(f"r-{ticket}-{at}", "b", ticket, "qa", outcome, at, {})


def test_an_unavailable_ledger_gives_empty_kpis() -> None:
    assert pipeline_kpi(LedgerView(unavailable="no ledger"), NOW) == PipelineKpi()


def test_kpis_come_from_the_ledger_and_never_from_demo_values() -> None:
    view = LedgerView(
        batches=[
            _batch("a", "active", "2026-11-06T06:00:00+00:00"),
            _batch("b", "awaiting-approval", "2026-11-06T09:00:00+00:00"),
            _batch("c", "blocked", "2026-11-05T12:00:00+00:00"),
            _batch("d", "failed", "2026-11-01T12:00:00+00:00"),
            _batch(
                "e",
                "completed",
                "2026-11-04T12:00:00+00:00",
                pr="2026-11-05T12:00:00+00:00",
            ),
        ],
        stages=[
            _stage("a", "developer", "2026-11-06T06:30:00+00:00"),
            _stage("a", "developer", "2026-11-06T07:00:00+00:00"),
            _stage("c", "qa", "2026-11-05T13:00:00+00:00"),
        ],
        reports=[
            _qa("#1", "failed", "2026-11-05T01:00:00+00:00"),
            _qa("#1", "completed", "2026-11-05T02:00:00+00:00"),
            _qa("#2", "completed", "2026-11-05T03:00:00+00:00"),
        ],
    )
    kpi = pipeline_kpi(view, NOW)
    assert kpi.wip == 3 and kpi.oldest_wip_seconds == 24 * 3600
    assert kpi.awaiting_approval == 1 and kpi.oldest_approval_seconds == 3 * 3600
    assert kpi.blocked == 1 and kpi.failed == 1
    # Batch "a" last moved five hours ago: under the six-hour limit.
    assert kpi.stale == 0
    assert kpi.rework == 1
    assert (kpi.qa_first_pass, kpi.qa_tickets) == (1, 2)
    assert kpi.cycle_p50_seconds == 24 * 3600 == kpi.cycle_p95_seconds
    assert kpi.throughput_7d == 1


def test_an_active_batch_without_recent_activity_is_stale() -> None:
    view = LedgerView(
        batches=[_batch("a", "active", "2026-11-06T01:00:00+00:00")],
        stages=[_stage("a", "developer", "2026-11-06T02:00:00+00:00")],
    )
    assert pipeline_kpi(view, NOW).stale == 1


def test_the_payload_round_trips_and_rejects_foreign_shapes() -> None:
    kpi = PipelineKpi(wip=2, oldest_wip_seconds=60, rework=1)
    assert pipeline_kpi_from_payload(kpi.to_payload()) == kpi
    with pytest.raises(ValueError):
        pipeline_kpi_from_payload({"wip": 1})
    with pytest.raises(ValueError):
        pipeline_kpi_from_payload({**kpi.to_payload(), "wip": "2"})
    with pytest.raises(ValueError):
        pipeline_kpi_from_payload({**kpi.to_payload(), "wip": None})


def test_duration_text_names_the_two_largest_units() -> None:
    assert duration_text(None) == "—"
    assert duration_text(59) == "0 мин"
    assert duration_text(3 * 3600 + 20 * 60) == "3 ч 20 мин"
    assert duration_text(2 * 86400 + 4 * 3600, "en") == "2 d 4 h"


def _report(dispatch: str, body: JsonObject, at: str) -> ReportEntry:
    return ReportEntry(dispatch, "b", "#1", "developer", "completed", at, body)


_NONE: JsonObject = {"status": "none", "details": ""}


def test_reports_kpi_reads_the_whole_bodies_and_the_dispatch_time() -> None:
    complete = _report(
        "d-1",
        {
            "output": "done",
            "risks": _NONE,
            "blockers": {"status": "present", "details": "x"},
        },
        "2026-11-06T10:00:00+00:00",
    )
    broken = _report(
        "d-2",
        {"output": "", "risks": _NONE, "blockers": _NONE},
        "2026-11-06T11:00:00+00:00",
    )
    view = LedgerView(
        reports=[complete, broken],
        stages=[
            StageEntry(
                "d-1",
                "b",
                "#1",
                "developer",
                "reported",
                "2026-11-06T10:00:00+00:00",
                complete,
            ),
        ],
        _dispatches={"d-1": {"created_at": "2026-11-06T09:00:00+00:00"}},
    )
    kpi = reports_kpi(view)
    assert kpi.reports == 2 and kpi.evidence_complete == 1
    assert kpi.blocked == 1 and kpi.attention == 0
    assert kpi.latency_p50_seconds == 3600
    assert reports_kpi_from_payload(kpi.to_payload()) == kpi
    assert reports_kpi(LedgerView(unavailable="x")) == ReportsKpi()
    with pytest.raises(ValueError):
        reports_kpi_from_payload({"reports": 1})


def test_analytics_come_from_the_ledger_and_round_trip() -> None:
    view = LedgerView(
        batches=[
            _batch("a", "active", "2026-11-04T12:00:00+00:00"),
            _batch("b", "awaiting-approval", "2026-11-06T09:00:00+00:00"),
            _batch(
                "e",
                "completed",
                "2026-11-04T12:00:00+00:00",
                pr="2026-11-06T08:00:00+00:00",
            ),
        ],
        stages=[
            _stage("a", "developer", "2026-11-06T06:30:00+00:00"),
            _stage("a", "developer", "2026-11-06T07:00:00+00:00"),
        ],
    )
    analytics = pipeline_analytics(view, NOW)
    assert analytics.flow["by_state"] == {
        "active": 1,
        "awaiting-approval": 1,
        "completed": 1,
    }
    assert analytics.flow["aging"] == {"lt_1d": 1, "d1_3": 1, "d3_7": 0, "gt_7d": 0}
    assert analytics.flow["pr_per_day"] == [0, 0, 0, 0, 0, 0, 1]
    assert analytics.quality["rework_by_role"] == {"developer": 1}
    assert analytics.runtime["unfinished"] == 2
    assert (
        analytics.gates["awaiting"] == 1
        and analytics.gates["approval_oldest_seconds"] == 3 * 3600
    )
    assert pipeline_analytics_from_payload(analytics.to_payload()) == analytics
    assert pipeline_analytics(LedgerView(unavailable="x"), NOW).flow == {}
    with pytest.raises(ValueError):
        pipeline_analytics_from_payload({"flow": {}})
    with pytest.raises(ValueError):
        pipeline_analytics_from_payload({**analytics.to_payload(), "flow": {"x": "y"}})


def _timed(
    batch_id: str, role: str, started: str, reported: str = "", body: JsonObject | None = None
) -> StageEntry:
    dispatch = f"d-{batch_id}-{role}-{started}"
    report = (
        ReportEntry(dispatch, batch_id, f"#{batch_id}", role, "completed", reported, body or {})
        if reported
        else None
    )
    return StageEntry(
        dispatch,
        batch_id,
        f"#{batch_id}",
        role,
        "reported" if reported else "working",
        reported or started,
        report,
        started_at=started,
    )


def test_unknown_rework_share_and_flow_efficiency_come_from_the_ledger() -> None:
    view = LedgerView(
        batches=[
            _batch("a", "mystery", "2026-11-06T06:00:00+00:00"),
            _batch(
                "b", "completed", "2026-11-06T00:00:00+00:00", pr="2026-11-06T10:00:00+00:00"
            ),
        ],
        stages=[
            _timed("b", "developer", "2026-11-06T01:00:00+00:00", "2026-11-06T03:00:00+00:00"),
            _timed("b", "developer", "2026-11-06T04:00:00+00:00", "2026-11-06T05:00:00+00:00"),
            _timed("b", "qa", "2026-11-06T06:00:00+00:00", "2026-11-06T07:00:00+00:00"),
        ],
    )
    kpi = pipeline_kpi(view, NOW)
    assert (kpi.unknown, kpi.batches, kpi.rework_batches) == (1, 2, 1)
    # Four worker hours out of a ten-hour cycle.
    assert kpi.flow_efficiency_pct == 40
    assert pipeline_kpi(LedgerView(batches=view.batches[:1]), NOW).flow_efficiency_pct is None


def test_role_analytics_findings_heartbeats_and_gate_latency() -> None:
    review = {
        "review": {
            "standards": {"findings": [{"severity": "warning"}, {"severity": "info"}]},
            "spec": {"findings": [{"severity": "warning"}]},
        }
    }
    open_stage = StageEntry(
        "d-open",
        "b",
        "#b",
        "qa",
        "working",
        "2026-11-06T11:30:00+00:00",
        started_at="2026-11-06T11:30:00+00:00",
        heartbeat_at="2026-11-06T09:00:00+00:00",
    )
    view = LedgerView(
        batches=[_batch("b", "active", "2026-11-06T00:00:00+00:00")],
        stages=[
            _timed("b", "developer", "2026-11-06T01:00:00+00:00", "2026-11-06T02:00:00+00:00"),
            _timed(
                "b", "code-review", "2026-11-06T02:10:00+00:00", "2026-11-06T02:40:00+00:00", review
            ),
            open_stage,
        ],
        _batch_records={
            "b": {
                "coordinator_decisions": [
                    {"decision": "accept", "approved_at": "2026-11-06T02:50:00+00:00"}
                ]
            }
        },
    )
    view.reports.extend(stage.report for stage in view.stages if stage.report)
    analytics = pipeline_analytics(view, NOW)
    assert analytics.flow["current_by_role"] == {"qa": 1}
    assert analytics.flow["aging_by_role"] == {"qa:m15_60": 1}
    assert analytics.flow["stage_p50_by_role"] == {"code-review": 1800, "developer": 3600}
    assert analytics.flow["wait_p50_by_role"] == {"code-review": 600, "qa": 31800}
    assert analytics.quality["findings_by_severity"] == {"warning": 2, "info": 1}
    assert analytics.runtime["heartbeat_age_p95_seconds"] == 3 * 3600
    assert analytics.runtime["stale_dispatches"] == 1
    assert analytics.runtime["open_age_by_role"] == {"qa": 1800}
    assert analytics.gates["decisions_by_verdict"] == {"accept": 1}
    assert analytics.gates["latency_p50_by_gate"] == {"code-review": 600}
    assert pipeline_analytics_from_payload(analytics.to_payload()) == analytics


def test_a_qa_report_without_its_own_run_log_is_stale_evidence() -> None:
    stage = _timed("b", "qa", "2026-11-06T01:00:00+00:00", "2026-11-06T02:00:00+00:00")
    assert stage.report is not None
    view = LedgerView(
        batches=[_batch("b", "active", "2026-11-06T00:00:00+00:00")],
        reports=[stage.report],
        stages=[stage],
    )
    assert reports_kpi(view).stale_evidence == 1
    assert reports_kpi_from_payload(reports_kpi(view).to_payload()).stale_evidence == 1


def _run(dispatch_id: str, logged: str) -> QaRun:
    return QaRun("qa.log", logged, dispatch_id, "#t", "passed", [], [], 0)


def _evidence_view() -> LedgerView:
    """Four batches: "p" with a QA run after its QA dispatch started and after the last developer
    report, "s1" whose run predates its own QA dispatch, "s2" whose run predates a later developer
    report, and "m" without a QA report."""
    stages = [
        _timed("p", "developer", "2026-11-06T01:00:00+00:00", "2026-11-06T02:00:00+00:00"),
        _timed("p", "code-review", "2026-11-06T02:10:00+00:00", "2026-11-06T02:30:00+00:00"),
        _timed("p", "qa", "2026-11-06T03:00:00+00:00", "2026-11-06T04:00:00+00:00"),
        _timed("s1", "qa", "2026-11-06T03:00:00+00:00", "2026-11-06T04:00:00+00:00"),
        _timed("s2", "qa", "2026-11-06T03:00:00+00:00", "2026-11-06T04:00:00+00:00"),
        _timed("s2", "developer", "2026-11-06T04:10:00+00:00", "2026-11-06T05:00:00+00:00"),
        _timed("m", "developer", "2026-11-06T01:00:00+00:00", "2026-11-06T02:00:00+00:00"),
    ]
    view = LedgerView(
        batches=[
            _batch(name, "active", "2026-11-06T00:00:00+00:00") for name in ("p", "s1", "s2", "m")
        ],
        stages=stages,
        qa_runs=[
            _run("d-p-qa-2026-11-06T03:00:00+00:00", "2026-11-06T03:50:00+00:00"),
            _run("d-s1-qa-2026-11-06T03:00:00+00:00", "2026-11-06T02:50:00+00:00"),
            _run("d-s2-qa-2026-11-06T03:00:00+00:00", "2026-11-06T03:50:00+00:00"),
        ],
    )
    view.reports.extend(stage.report for stage in stages if stage.report)
    return view


def test_the_evidence_matrix_has_one_qa_run_definition_per_batch() -> None:
    rows = {row.batch_id: row for row in evidence_matrix(_evidence_view())}
    assert rows["p"] == EvidenceRow("p", "#p", "present", "present", "present", "present")
    assert rows["s1"].qa_run == "stale" and rows["s1"].developer == "missing"
    assert rows["s2"].qa_run == "stale" and rows["s2"].developer == "present"
    assert rows["m"] == EvidenceRow("m", "#m", "present", "missing", "missing", "missing")
    assert {(row.receipt, row.publish) for row in rows.values()} == {("none", "none")}
    assert list(rows) == ["p", "s1", "s2", "m"]


def test_the_stale_evidence_kpi_counts_the_stale_cells_of_the_matrix() -> None:
    view = _evidence_view()
    stale = sum(row.qa_run == "stale" for row in evidence_matrix(view))
    assert reports_kpi(view).stale_evidence == stale == 2
    assert evidence_matrix(LedgerView(unavailable="none")) == ()


def _decided(batch_id: str, reported: str, approved: str) -> tuple[StageEntry, JsonObject]:
    stage = _timed(batch_id, "qa", reported, reported)
    return stage, {"coordinator_decisions": [{"decision": "accept", "approved_at": approved}]}


def test_the_gate_latency_trend_is_hourly_over_the_last_day() -> None:
    pairs = [
        # 10 and 30 minutes in the last hour, 20 minutes three hours ago, one older than a day.
        _decided("a", "2026-11-06T11:20:00+00:00", "2026-11-06T11:30:00+00:00"),
        _decided("b", "2026-11-06T11:15:00+00:00", "2026-11-06T11:45:00+00:00"),
        _decided("c", "2026-11-06T08:10:00+00:00", "2026-11-06T08:30:00+00:00"),
        _decided("d", "2026-11-05T10:00:00+00:00", "2026-11-05T11:00:00+00:00"),
    ]
    view = LedgerView(
        batches=[_batch(name, "active", "2026-11-05T00:00:00+00:00") for name in "abcd"],
        stages=[stage for stage, _ in pairs],
        _batch_records={stage.batch_id: record for stage, record in pairs},
    )
    view.reports.extend(stage.report for stage, _ in pairs if stage.report)
    analytics = pipeline_analytics(view, NOW)
    p50, p95 = analytics.gates["latency_p50_by_hour"], analytics.gates["latency_p95_by_hour"]
    assert isinstance(p50, list) and isinstance(p95, list)
    assert len(p50) == len(p95) == 24
    assert (p50[23], p95[23]) == (600, 1800)
    assert (p50[20], p95[20]) == (1200, 1200)
    assert [index for index, value in enumerate(p50) if value is not None] == [20, 23]
    assert pipeline_analytics_from_payload(analytics.to_payload()) == analytics
