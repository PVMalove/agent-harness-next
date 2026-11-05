"""A console server client for tests: answers the Home snapshot from injected collect seams, the
way the server builds it, and the screen snapshots from an injected ledger and fake lock, recovery
and route facts passed through the same payload codecs the server uses, so no test opens a
socket."""

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
from harness.console.kernel.home_snapshot import (
    HomeContext,
    HomeSnapshot,
    build_home_snapshot,
)
from harness.console.tui.client import (
    JobResult,
    LockUnavailable,
    OrchestrationView,
    RecoveryFacts,
    RouteFacts,
)
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
        self.closed = False

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot:
        self.requests.append((force, online))
        return build_home_snapshot(
            self._collect_dashboard(self.repo, online=online),
            self._collect_context(self.repo),
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

    def run_job(
        self, command_id: str, values: Mapping[str, str], *, confirmed: bool = False
    ) -> JobResult:
        self.screen_requests.append(("job", command_id, dict(values), confirmed))
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
