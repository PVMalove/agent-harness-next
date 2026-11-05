"""A console server client for tests: answers the Home snapshot from injected collect seams, the
way the server builds it, so no Pilot test opens a socket."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from harness.console.kernel import data as console_data
from harness.console.backend.infrastructure import home_facts
from harness.console.kernel.data import DashboardData
from harness.console.kernel.home_snapshot import HomeContext, HomeSnapshot, build_home_snapshot


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
    ) -> None:
        self.repo = repo
        self._collect_dashboard = collect_dashboard
        self._collect_context = collect_context
        self.requests: list[tuple[bool, bool]] = []
        self.closed = False

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot:
        self.requests.append((force, online))
        return build_home_snapshot(
            self._collect_dashboard(self.repo, online=online),
            self._collect_context(self.repo),
        )

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
