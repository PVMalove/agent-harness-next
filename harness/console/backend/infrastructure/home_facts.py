"""Home facts read from the project: the dashboard checks and the context cards."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from ...kernel.data import DashboardData, collect_dashboard
from ...kernel.home_snapshot import HomeContext, HomeSnapshot, build_home_snapshot
from ...kernel.repo_map import cached_map, head_commit
from ...kernel.repo_map_settings import memory_status


def collect_context(repo: Path) -> HomeContext:
    """Read the Repo Map cached for the project's HEAD and the memory status; builds nothing."""
    head = head_commit(repo)
    return HomeContext(
        repo_map=cached_map(repo, head) if head else None, memory=memory_status(repo)
    )


class _CollectDashboard(Protocol):
    def __call__(self, repo: Path, /) -> DashboardData: ...


class _CollectOnlineDashboard(Protocol):
    def __call__(self, repo: Path, /, *, online: bool) -> DashboardData: ...


def collect_home(
    repo: Path,
    *,
    online: bool = False,
    dashboard: _CollectDashboard | _CollectOnlineDashboard = collect_dashboard,
    context: Callable[[Path], HomeContext] = collect_context,
) -> HomeSnapshot:
    """Run the offline checks (with `online`, the online ones too) and read the context cards;
    blocks until both are done. `dashboard` gets `online=True` only for an online collect."""
    # An offline seam takes the repository only; the online flag goes to an online collect alone.
    data = (
        cast(_CollectOnlineDashboard, dashboard)(repo, online=True)
        if online
        else cast(_CollectDashboard, dashboard)(repo)
    )
    return build_home_snapshot(data, context(repo))
