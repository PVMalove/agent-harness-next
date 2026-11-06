"""A console server client for tests: answers the Home snapshot from injected collect seams, the
way the server builds it, and the screen snapshots from an injected ledger and fake lock, recovery,
route, health and Harness facts passed through the same payload codecs the server uses, so no
test opens a socket."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from harness.console.backend.infrastructure import home_facts
from harness.console.kernel import data as console_data
from harness.console.kernel import reports as ledger
from harness.console.kernel.batch_history import History
from harness.console.kernel.container_route import Authored
from harness.console.kernel.data import DashboardData
from harness.console.kernel.harness_facts import HarnessState, harness_state
from harness.console.kernel.health_report import report_from_payload
from harness.console.kernel.home_snapshot import (
    HomeContext,
    HomeSnapshot,
    build_home_snapshot,
)
from harness.console.kernel.help_text import HelpSections, help_sections
from harness.console.kernel.maintenance import MaintenanceView
from harness.console.kernel.open_project_snapshot import OpenProjectFacts
from harness.console.kernel.repo_map_settings import MemoryStatus, TierSetting
from harness.console.kernel.repo_map_snapshot import RepoMapFacts
from harness.console.kernel.task_board import BoardSnapshot, BoardSpec, BoardSpecs
from harness.console.tui.client import (
    HarnessFacts,
    JobResult,
    LockUnavailable,
    OrchestrationView,
    RecoveryFacts,
    RouteFacts,
)
from harness.health.model import Report
from harness.health.report_json import to_json
from harness.orchestration.ledger.lifecycle import JsonObject


def _wire(payload: object) -> object:
    """`payload` as a client reads it back from the JSON text of a reply."""
    return json.loads(json.dumps(payload))


class CollectDashboard(Protocol):
    def __call__(self, repo: Path, /, *, online: bool = False) -> DashboardData: ...


def _real_dashboard(repo: Path, *, online: bool = False) -> DashboardData:
    # Through the module: a test that patches `data.collect_dashboard` is seen here too.
    return console_data.collect_dashboard(repo, online=online)


def _real_context(repo: Path) -> HomeContext:
    return home_facts.collect_context(repo)


class FakeHomeClient:
    """Records `(force, online)` of every request and answers with the snapshot of the facts."""

    def __init__(
        self,
        repo: Path,
        collect_dashboard: CollectDashboard = _real_dashboard,
        collect_context: Callable[[Path], HomeContext] = _real_context,
        *,
        load_ledger: Callable[[Path], ledger.LedgerView] = ledger.load_ledger_view,
        lock: JsonObject | str | None = None,
    ) -> None:
        self.repo = repo
        self._collect_dashboard = collect_dashboard
        self._collect_context = collect_context
        self._load_ledger = load_ledger
        # The ledger lock state, or the text of why the server could not read it.
        self.lock: JsonObject | str = {"locked": False} if lock is None else lock
        self.requests: list[tuple[bool, bool]] = []
        self.screen_requests: list[tuple[object, ...]] = []
        self.recovery_facts = RecoveryFacts(History(), None)
        self.route_facts = RouteFacts(Authored(None, "нет конфигурации"), None)
        self.job_result = JobResult("completed", 0, "{}", "", False, None)
        self.health = Report(1, str(repo), False)
        self.drift = "clean"
        self.maintenance: tuple[MaintenanceView | None, str] = (None, "")
        self.repo_map_facts = RepoMapFacts(
            None, None, TierSetting("full", False), MemoryStatus(False, False, (), None), None, {}
        )
        self.open_project_facts = OpenProjectFacts(
            str(repo), None, "Это не Git-проект", {}, ()
        )
        self.closed = False

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot:
        self.requests.append((force, online))
        return build_home_snapshot(
            self._collect_dashboard(self.repo, online=online),
            self._collect_context(self.repo),
        )

    def task_board_specs(self, *, force: bool = False) -> BoardSpecs:
        self.screen_requests.append(("task_board.specs", force))
        return BoardSpecs("github", (), None, None, False)

    def task_board(self, spec: str, *, force: bool = False) -> BoardSnapshot:
        self.screen_requests.append(("task_board", spec, force))
        return BoardSnapshot(
            tracker="github",
            ledger="ok",
            spec=BoardSpec(spec, 0, spec, None, None),
            columns=("backlog", "ready", "progress", "review", "done"),
            kpis={"open": 0, "total": 0, "with_open_blockers": 0, "active_batch": 0},
            tickets=(),
            truncated=False,
        )

    def reports(self, *, force: bool = False, online: bool = False) -> ledger.LedgerView:
        self.screen_requests.append(("reports", force, online))
        view = self._load_ledger(self.repo)
        return ledger.ledger_from_payload(_wire(ledger.ledger_payload(view)))

    def report(self, dispatch_id: str) -> JsonObject | None:
        self.screen_requests.append(("report", dispatch_id))
        view = self._load_ledger(self.repo)
        found = next(
            (entry for entry in view.reports if entry.dispatch_id == dispatch_id), None
        )
        return None if found is None else found.report

    def timeline(self, batch_id: str) -> ledger.BatchTimeline | None:
        self.screen_requests.append(("timeline", batch_id))
        timeline = self._load_ledger(self.repo).timeline(batch_id)
        if timeline is None:
            return None
        return ledger.timeline_from_payload(_wire(ledger.timeline_payload(timeline)))

    def orchestration(self, *, force: bool = False) -> OrchestrationView:
        view = self.reports(force=force)
        if isinstance(self.lock, str):
            return OrchestrationView(view, None, self.lock)
        return OrchestrationView(view, self.lock, None)

    def ledger_lock(self) -> JsonObject:
        self.screen_requests.append(("lock",))
        if isinstance(self.lock, str):
            raise LockUnavailable(self.lock)
        return self.lock

    def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> RecoveryFacts:
        self.screen_requests.append(("recovery", batch, tuple(skip)))
        return self.recovery_facts

    def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> RouteFacts:
        self.screen_requests.append(("route", batch, role, runtime))
        return self.route_facts

    def diagnostics(self, *, online: bool = False, force: bool = False) -> Report:
        self.screen_requests.append(("diagnostics", online, force))
        report = Report(
            self.health.schema_version,
            self.health.repo,
            online,
            list(self.health.checks),
            list(self.health.fixes_applied),
        )
        return report_from_payload(_wire(to_json(report)))

    def harness(self, *, force: bool = False) -> HarnessFacts:
        self.screen_requests.append(("harness", force))
        state = HarnessState.from_payload(_wire(harness_state(self.repo).to_payload()))
        return HarnessFacts(
            state, console_data.harness_version(), self.drift, self.reports()
        )

    def harness_maintenance(
        self, *, force: bool = False
    ) -> tuple[MaintenanceView | None, str]:
        self.screen_requests.append(("maintenance", force))
        view, error = self.maintenance
        if view is None:
            return None, error
        return MaintenanceView.from_payload(_wire(view.to_payload())), error

    def repo_map(self, *, force: bool = False) -> RepoMapFacts:
        self.screen_requests.append(("repo_map", force))
        return RepoMapFacts.from_payload(_wire(self.repo_map_facts.to_payload()))

    def open_project(self, *, force: bool = False) -> OpenProjectFacts:
        self.screen_requests.append(("open_project", force))
        return OpenProjectFacts.from_payload(
            _wire(self.open_project_facts.to_payload())
        )

    def help(self, language: str) -> HelpSections:
        self.screen_requests.append(("help", language))
        return HelpSections.from_payload(_wire(help_sections(language).to_payload()))

    def run_job(
        self,
        command_id: str,
        values: Mapping[str, str],
        *,
        confirmed: bool = False,
        confirmation: str | None = None,
        plan_digest: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
    ) -> JobResult:
        self.screen_requests.append(("job", command_id, dict(values), confirmed))
        if confirmation is not None or plan_digest is not None:
            self.screen_requests.append(("job-extra", confirmation, plan_digest))
        if on_output is not None and self.job_result.stdout:
            on_output("stdout", self.job_result.stdout)
        return self.job_result

    def close(self) -> None:
        self.closed = True


def fake_home(
    collect_dashboard: CollectDashboard,
    collect_context: Callable[[Path], HomeContext] | None = None,
    *,
    repo: Path = Path("."),
) -> FakeHomeClient:
    """A fake client over `collect_dashboard` and `collect_context` (the real one by default);
    `repo` is what they are called with."""
    return FakeHomeClient(repo, collect_dashboard, collect_context or _real_context)
