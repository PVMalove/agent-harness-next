"""The pipeline KPIs the server computes from the ledger."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from harness.json_types import JsonObject
from harness.console.kernel.pipeline_kpi import (
    PipelineKpi,
    ReportsKpi,
    duration_text,
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
