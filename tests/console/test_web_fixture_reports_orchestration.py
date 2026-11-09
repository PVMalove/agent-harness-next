"""The fixture snapshots of the Web Reports, Orchestration, Recovery and Container route pages
are what the server sends for one in-memory ledger and fake core answers, they decode with the TUI
decoders, and each facts file lists what the TUI shows for its fixture. A drift on either side
fails here. `python -m tests.console.test_web_fixture_reports_orchestration` rewrites them."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from harness.console.kernel import reports as console_reports
from harness.console.kernel.pipeline_kpi import (
    evidence_payload,
    pipeline_analytics,
    pipeline_analytics_from_payload,
    pipeline_kpi,
    pipeline_kpi_from_payload,
    reports_kpi,
    reports_kpi_from_payload,
)
from harness.console.kernel.publish_view import publish_payload
from harness.console.kernel.reports import (
    BatchSummary,
    LedgerView,
    QaAttempt,
    QaRun,
    ReportEntry,
    StageEntry,
    ledger_from_payload,
    ledger_payload,
    timeline_from_payload,
    timeline_payload,
)
from harness.console.kernel.batch_history import History, HistoryBatch
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, Outcome
from harness.console.kernel.screen_views import (
    recovery_view_payload,
    route_view_payload,
)
from harness.console.tui import stats
from harness.console.tui.ledger_lock import lock_text
from harness.json_types import JsonObject

from .test_console_container_route import (
    AUTHORED_DOCUMENT,
    preflight_document,
    verification,
)
from .test_console_recovery_view import actions, diagnostic, status_document

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"
NOW = datetime(2026, 11, 8, 13, 0, tzinfo=UTC)
NONE: JsonObject = {"status": "none", "details": ""}

QA_BODY: JsonObject = {
    "output": "QA остановился на pytest: один тест упал.",
    "checks_run": [
        {
            "command": "make lint",
            "result": "pass",
            "evidence": "ruff и mypy без замечаний",
        },
        {
            "command": "pytest -q tests/console",
            "result": "fail",
            "evidence": "1 failed",
        },
        {"command": "npm run test:e2e", "result": "not_run", "evidence": ""},
    ],
    "risks": NONE,
    "blockers": {
        "status": "present",
        "details": "Падает test_reports_kpi: нужен фикс разработчика.",
    },
    "next_coordinator_action": "developer-retry",
    "commit_sha": "c0ffee1",
    "changed_files": ["harness/console/kernel/reports.py"],
}
REVIEW_BODY: JsonObject = {
    "output": "Ревью: одно замечание по спецификации.",
    "checks_run": [],
    "review": {
        "candidate_commit": "c0ffee1",
        "standards": {"severity": "none", "findings": []},
        "spec": {
            "severity": "warning",
            "findings": [
                {
                    "severity": "warning",
                    "summary": "нет подписи en",
                    "evidence": "reports.py:12",
                }
            ],
        },
    },
    "risks": {"status": "present", "details": "Подписи en не проверены."},
    "blockers": NONE,
    "next_coordinator_action": "qa",
}
LOCK: JsonObject = {
    "locked": True,
    "operation": "report submit",
    "owner": {"pid": 4242, "host": "build-1"},
    "held_seconds": 75,
    "remaining_seconds": 525,
    "verdict": "owner-alive",
    "release_available": False,
}


def ledger() -> LedgerView:
    """Two batches: an active one with a developer, a review and a failed QA report and a stage
    still at work, and a completed one whose PR was opened."""
    reports = [
        ReportEntry(
            "d-qa",
            "b-887",
            "#887",
            "qa",
            "failed",
            "2026-11-08T12:00:00+00:00",
            QA_BODY,
        ),
        ReportEntry(
            "d-rev",
            "b-887",
            "#887",
            "review",
            "completed",
            "2026-11-08T11:00:00+00:00",
            REVIEW_BODY,
        ),
        ReportEntry(
            "d-dev",
            "b-887",
            "#887",
            "developer",
            "completed",
            "2026-11-08T10:00:00+00:00",
            {
                "output": "Страница «Отчёты» готова.",
                "checks_run": [
                    {"command": "make lint", "result": "pass", "evidence": ""}
                ],
                "risks": NONE,
                "blockers": NONE,
                "next_coordinator_action": "review",
            },
        ),
        ReportEntry(
            "d-old",
            "b-886",
            "#886",
            "developer",
            "completed",
            "2026-11-01T09:00:00+00:00",
            {"output": "Готово.", "risks": NONE, "blockers": NONE},
        ),
    ]
    dispatches: dict[str, JsonObject] = {
        "d-dev": {"role": "developer", "created_at": "2026-11-08T09:10:00+00:00"},
        "d-rev": {"role": "review", "created_at": "2026-11-08T10:20:00+00:00"},
        "d-qa": {"role": "qa", "created_at": "2026-11-08T11:15:00+00:00"},
        "d-wip": {"role": "developer", "created_at": "2026-11-08T11:30:00+00:00"},
        "d-old": {"role": "developer", "created_at": "2026-11-01T08:10:00+00:00"},
    }
    states = {
        "d-dev": "reported",
        "d-rev": "reported",
        "d-qa": "reported",
        "d-wip": "working",
        "d-old": "reported",
    }
    batches = [
        BatchSummary(
            "b-887",
            "#887",
            "active",
            "2026-11-08T09:00:00+00:00",
            branch="feature/issue-887",
            pr_state="missing",
        ),
        BatchSummary(
            "b-886",
            "#886",
            "completed",
            "2026-11-01T08:00:00+00:00",
            branch="feature/issue-886",
            pr_created_at="2026-11-02T10:30:00+00:00",
            pr_url="https://example.com/pull/1011",
            pr_state="found",
        ),
    ]
    records: dict[str, JsonObject] = {
        "b-887": {
            "batch_id": "b-887",
            "ticket": "#887",
            "state": "active",
            "dispatches": [
                {
                    "dispatch_id": key,
                    "role": dispatches[key]["role"],
                    "state": states[key],
                }
                for key in ("d-dev", "d-rev", "d-qa", "d-wip")
            ],
            "coordinator_decisions": [
                {
                    "decision": "developer-retry",
                    "next_role": "developer",
                    "approved_by": "policy:auto",
                    "approved_at": "2026-11-08T12:10:00+00:00",
                    "note": "QA упал",
                }
            ],
        },
        "b-886": {
            "batch_id": "b-886",
            "ticket": "#886",
            "state": "completed",
            "dispatches": [
                {"dispatch_id": "d-old", "role": "developer", "state": "reported"}
            ],
        },
    }
    view = LedgerView(
        reports=reports,
        batches=batches,
        qa_runs=[
            QaRun(
                "qa-run-1.log",
                "2026-11-08T11:58:00+00:00",
                "d-qa",
                "#887",
                "failed",
                [("make lint", 0), ("pytest -q tests/console", 1)],
                ["E   assert 3 == 2", "FAILED tests/console/test_reports.py::test_kpi"],
                42,
            )
        ],
        qa_attempts=[
            QaAttempt(
                "d-qa", "collect", "2026-11-08T11:40:00+00:00", "лог QA не найден"
            )
        ],
        _batch_records=records,
        _dispatches=dispatches,
    )
    by_id = {entry.dispatch_id: entry for entry in reports}
    for dispatch_id, record in dispatches.items():
        report = by_id.get(dispatch_id)
        view.stages.append(
            StageEntry(
                dispatch_id,
                report.batch_id if report else "b-887",
                report.ticket if report else "#887",
                str(record["role"]),
                states[dispatch_id],
                report.reported_at if report else str(record["created_at"]),
                report,
                started_at=str(record["created_at"]),
                heartbeat_at=""
                if report
                else _shifted(str(record["created_at"]), minutes=5),
            )
        )
    view.stages[:] = console_reports.select_stages(view.stages)
    return view


def _shifted(moment: str, *, minutes: int) -> str:
    """`moment` moved by `minutes`, in the same ISO form."""
    return (datetime.fromisoformat(moment) + timedelta(minutes=minutes)).isoformat()


class FixtureGit:
    """Local refs of the fixture: the issue branch points at the reviewed candidate."""

    def tip(self, branch: str) -> str | None:
        return "c0ffee1" if branch else None

    def is_ancestor(self, older: str, newer: str) -> bool | None:
        return True


def reports_payload(view: LedgerView) -> JsonObject:
    """The reports.snapshot payload, as `ScreenService` builds it."""
    return {
        **ledger_payload(view),
        "reports_kpi": reports_kpi(view).to_payload(),
        "publish": publish_payload(view, FixtureGit()),
        "evidence": evidence_payload(view),
    }


def orchestration_payload(view: LedgerView) -> JsonObject:
    """The orchestration.snapshot payload, as `ScreenService.orchestration` builds it."""
    return {
        "ledger": reports_payload(view),
        "lock": {"lock": LOCK, "error": None},
        "kpi": pipeline_kpi(view, NOW).to_payload(),
        "analytics": pipeline_analytics(view, NOW).to_payload(),
    }


def report_facts(payload: object, body: JsonObject, timeline: object) -> list[str]:
    """What the TUI Reports screen shows for the reports fixture with its newest stage (the QA
    report) selected and the active batch opened: the KPI tiles, the stage and batch rows, the
    report sections, the QA log and the batch chronology."""
    view = ledger_from_payload(payload)
    assert view.reports_kpi is not None
    facts: list[str] = []
    for label, figure, hint, _ in stats.reports_kpi_tiles(
        reports_kpi_from_payload(view.reports_kpi), "ru"
    ):
        facts += [label, figure] + ([hint] if hint else [])
    for stage in console_reports.select_stages(view.stages):
        facts.append(console_reports.stage_status(stage).render("ru"))
    for batch in view.batches:
        facts += [
            console_reports.batch_status(batch).render("ru"),
            console_reports.batch_start_text(batch),
            console_reports.batch_timing_text(batch),
        ]
    for title, lines in console_reports.report_section_lines(body):
        facts.append(title)
        for status, line in lines:
            if status is not None:
                facts.append(status.render("ru"))
            if line:
                facts.append(line)
    facts += [
        line.strip()
        for line in console_reports.qa_log_text(view, "d-qa").split("\n")
        if line.strip()
    ]
    chronology = timeline_from_payload(timeline)
    facts.append(console_reports.role_flow_text(chronology))
    facts += [event.text for event in chronology.events]
    return list(dict.fromkeys(facts))


def orchestration_facts(payload: JsonObject) -> list[str]:
    """What the TUI Orchestration screen shows for the orchestration fixture: the KPI tiles,
    every analytics tab, the state and statistics fields, the lock panel, the state filter and
    the batch history."""
    view = ledger_from_payload(payload["ledger"])
    facts: list[str] = []
    for label, figure, hint, _ in stats.kpi_tiles(
        pipeline_kpi_from_payload(payload["kpi"]), "ru"
    ):
        facts += [label, figure] + ([hint] if hint else [])
    analytics = pipeline_analytics_from_payload(payload["analytics"])
    for section in ("flow", "quality", "runtime", "gates"):
        for label, value in stats.analytics_rows(section, analytics, "ru"):
            facts += [label, value]
    for label, value in stats.pipeline_stats_fields(stats.pipeline_stats(view)):
        facts += [label, value]
    lock = payload["lock"]
    assert isinstance(lock, dict) and isinstance(lock["lock"], dict)
    facts += lock_text(lock["lock"], "ru").split("\n")
    facts += [label for _, label in stats.state_filter_items(view)]
    for batch in view.batches:
        facts += [line.strip() for line in stats.batch_label(batch).split("\n")]
    return list(dict.fromkeys(facts))


HISTORY = History(
    (
        HistoryBatch(
            "b-887",
            "#887",
            "feature/issue-887",
            "active",
            "t2",
            False,
            4,
            1,
            "developer",
        ),
        HistoryBatch(
            "b-886", "#886", "feature/issue-886", "completed", "t1", True, 1, 0, ""
        ),
    )
)
RECOVERY_STATUS = ApiResult(
    Outcome.DOCUMENT,
    ("recovery", "status"),
    (
        status_document(
            batch_id="b-887",
            resumable=False,
            hold={
                "reason": "runtime",
                "message": "runtime удерживает batch после сбоя worker",
            },
            lifecycle={"state": "active", "stopped": True, "next_action": "developer"},
            diagnostics=[
                diagnostic(),
                diagnostic(
                    id="a1a1a1a1a1a1a1a1",
                    code="stale-snapshot",
                    check="snapshot",
                    fatal=False,
                    advisory="stale-snapshot",
                    message="snapshot старше конфигурации",
                    remedy="",
                    pointer="",
                    suggestion=None,
                ),
            ],
            actions=actions(fix=True, skip=True),
            next={"command": "recovery resume --batch b-887", "reason": "ok"},
        ),
    ),
    0,
)


def recovery_inputs() -> tuple[History, ApiResult, str, tuple[str, ...]]:
    """The batch history and the `recovery status` answer the recovery fixture is built from."""
    return HISTORY, RECOVERY_STATUS, "b-887", ()


def route_inputs() -> tuple[Authored, ApiResult, str, str, str]:
    """The authored configuration and the refused `dispatch preflight` answer the container
    route fixture is built from."""
    preflight = ApiResult(
        Outcome.REFUSED,
        ("dispatch", "preflight"),
        (preflight_document(verified=verification("unverified")),),
        2,
    )
    return Authored(AUTHORED_DOCUMENT), preflight, "b-887", "developer", ""


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.split("\n") if line.strip()]


def _body_facts(view: JsonObject) -> list[str]:
    """What `render_body` draws for a view: blockers, groups, rows, unavailable actions, notes,
    and the label of every action button."""
    facts: list[str] = []
    if view["blockers"]:
        facts.append("✖ Блокирует маршрут")
        for blocker in view["blockers"]:
            facts += _lines(blocker)
    for row in view["rows"]:
        facts += [row["group"], row["mark"], row["label"], *_lines(row["value"])]
    for action in view["actions"]:
        facts.append(action["label"])
        if not action["enabled"] and action["reason"]:
            facts.append(f"✖ недоступно: {action['label']} — {action['reason']}")
    for note in view["notes"]:
        facts += _lines(note)
    return [fact for fact in facts if fact]


def recovery_facts(payload: JsonObject) -> list[str]:
    """What the TUI Recovery screen shows for the recovery fixture once the batch is opened:
    the history labels, the recovery gate, the view's body and its action labels."""
    entry = payload["entry"]
    facts = [item["label"] for item in payload["history"]]
    facts.append(f"{entry['mark']}  {entry['reason']}")
    facts += _body_facts(payload["view"])
    return list(dict.fromkeys(facts))


def route_facts(payload: JsonObject) -> dict[str, list[str]]:
    """What the TUI Container route screen shows for the route fixture: the context strip and
    the tab labels on every tab, and each stage's body on its own tab."""
    common = [f"{label}: {value}" for label, value in payload["context"]]
    common += [f"{tab['mark'].split(' ')[0]} {tab['title']}" for tab in payload["tabs"]]
    facts: dict[str, list[str]] = {"common": list(dict.fromkeys(common))}
    for stage, view in payload["stages"].items():
        facts[stage] = list(dict.fromkeys(_body_facts(view)))
    return facts


def recovery_catalog() -> JsonObject:
    """The `job.catalog` reply body of the section `recovery`, as the composed job service lists
    it for a project with the coordinator script."""
    from harness.console.backend import composition
    from harness.console.backend.domain.approvals import CANCEL_REASON
    from harness.console.kernel.coordinator_catalog import _COORDINATOR_SCRIPT

    async def idle(*args: object, **kwargs: object) -> int:
        return 0

    with tempfile.TemporaryDirectory() as root:
        script = Path(root) / _COORDINATOR_SCRIPT
        script.parent.mkdir(parents=True)
        script.write_text("", encoding="utf-8")
        served = composition.job_service(Path(root), executor=idle)
        return {"commands": served.commands("recovery"), "cancel_reason": CANCEL_REASON}


def fixtures() -> JsonObject:
    """Every fixture file name with its content."""
    view = ledger()
    reports = reports_payload(view)
    timeline = view.timeline("b-887")
    assert timeline is not None
    chronology = timeline_payload(timeline)
    orchestration = orchestration_payload(view)
    return {
        "reports.json": reports,
        "reports-report.json": QA_BODY,
        "reports-timeline.json": chronology,
        "reports-facts.json": report_facts(reports, QA_BODY, chronology),
        "orch-snapshot.json": orchestration,
        "orch-snapshot-facts.json": orchestration_facts(orchestration),
        "recovery.json": (recovery := recovery_view_payload(*recovery_inputs())),
        "recovery-facts.json": recovery_facts(recovery),
        "recovery-catalog.json": recovery_catalog(),
        "container-route.json": (route := route_view_payload(*route_inputs())),
        "container-route-facts.json": route_facts(route),
    }


def _text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _committed(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_every_committed_fixture_and_facts_file_equals_the_rendered_one() -> None:
    rendered = fixtures()
    assert sorted(
        path.name for path in FIXTURES.glob("*.json") if path.name in rendered
    ) == sorted(rendered)
    for name, value in rendered.items():
        assert (FIXTURES / name).read_text(encoding="utf-8") == _text(value), (
            f"{name} is out of date: run "
            "`python -m tests.console.test_web_fixture_reports_orchestration`"
        )


def test_the_ledger_fixtures_decode_with_the_tui_decoders() -> None:
    reports = ledger_from_payload(_committed("reports.json"))
    assert [stage.dispatch_id for stage in reports.stages] == [
        "d-qa",
        "d-wip",
        "d-rev",
        "d-dev",
        "d-old",
    ]
    assert reports.reports_kpi is not None
    assert reports_kpi_from_payload(reports.reports_kpi).reports == 4
    timeline = timeline_from_payload(_committed("reports-timeline.json"))
    assert timeline.batch.batch_id == "b-887"
    orchestration = _committed("orch-snapshot.json")
    assert isinstance(orchestration, dict)
    assert ledger_from_payload(orchestration["ledger"]).batches == reports.batches
    assert pipeline_kpi_from_payload(orchestration["kpi"]).wip == 1
    assert pipeline_analytics_from_payload(orchestration["analytics"]).flow
    assert lock_text(orchestration["lock"]["lock"]).startswith("Lock ledger занят")


def test_the_view_fixtures_are_the_kernel_projections_of_their_inputs() -> None:
    assert _committed("recovery.json") == recovery_view_payload(*recovery_inputs())
    assert _committed("container-route.json") == route_view_payload(*route_inputs())
    history, status, batch, _ = recovery_inputs()
    assert History.from_payload(history.to_payload()) == history
    assert ApiResult.from_payload(status.to_payload()) == status
    assert batch == "b-887"


def test_each_facts_file_is_what_the_tui_shows_for_its_fixture() -> None:
    reports = _committed("reports.json")
    body = _committed("reports-report.json")
    assert isinstance(body, dict)
    assert _committed("reports-facts.json") == report_facts(
        reports, body, _committed("reports-timeline.json")
    )
    orchestration = _committed("orch-snapshot.json")
    assert isinstance(orchestration, dict)
    assert _committed("orch-snapshot-facts.json") == orchestration_facts(orchestration)
    recovery = _committed("recovery.json")
    assert isinstance(recovery, dict)
    assert _committed("recovery-facts.json") == recovery_facts(recovery)
    route = _committed("container-route.json")
    assert isinstance(route, dict)
    assert _committed("container-route-facts.json") == route_facts(route)
    # A stage the QA report names carries the TUI's own status words.
    assert "✖ отчёт получен · ошибка" in report_facts(
        reports, body, _committed("reports-timeline.json")
    )


def main() -> None:
    for name, value in fixtures().items():
        (FIXTURES / name).write_text(_text(value), encoding="utf-8")


if __name__ == "__main__":
    main()
