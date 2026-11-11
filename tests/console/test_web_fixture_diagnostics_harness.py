"""The fixtures the Diagnostics and Harness Playwright specs replay are what the server sends:
the health report decodes as the `--json` contract, the maintenance facts as the TUI decodes
them, and the overview reply validates against the reply models."""

from __future__ import annotations

import json
from pathlib import Path

from harness.console.backend.api.schemas import REPLIES, HarnessOverviewReply
from harness.console.kernel.health_report import report_from_payload
from harness.console.kernel.maintenance import MaintenanceView
from harness.health.report_json import to_json

FIXTURES = Path(__file__).resolve().parents[1] / "web" / "fixtures"


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_the_diagnostics_fixture_is_a_health_report_of_every_status() -> None:
    payload = _fixture("diagnostics-report.json")
    report = report_from_payload(payload)
    assert to_json(report) == payload
    assert {check.status for check in report.checks} == {
        "ok",
        "warn",
        "fail",
        "skipped",
    }


def test_the_maintenance_fixture_decodes_with_its_digests_and_totals() -> None:
    payload = _fixture("harness-maintenance.json")
    assert isinstance(payload, dict) and set(payload) == {"maintenance", "error"}
    view = MaintenanceView.from_payload(payload["maintenance"])
    assert view.to_payload() == payload["maintenance"]
    assert view.hard.total.bytes > view.soft.total.bytes
    assert any(fact.reason == "" for fact in view.worktrees)


def test_the_overview_fixture_is_a_harness_overview_reply() -> None:
    payload = _fixture("harness-overview.json")
    assert isinstance(payload, dict)
    reply = {
        "v": 1,
        "id": 1,
        "type": "harness.overview",
        "ok": True,
        "cached": True,
        "age_seconds": 3.0,
        **payload,
    }
    assert isinstance(REPLIES.validate_python(reply), HarnessOverviewReply)
    # The e2e Adapters block reads the wire's integrations, not a "no data" placeholder.
    assert [item["name"] for item in payload["integrations"]] == ["Claude Code", "Codex", "GitHub"]
