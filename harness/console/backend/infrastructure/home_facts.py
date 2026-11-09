"""Home facts read from the project: the dashboard checks and the context cards."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from harness.health.project_tracker import resolve_project_tracker
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import (
    POINTER_NAME,
    STORE_LEDGER_VERSION,
    LifecycleLedger,
)

from ...kernel.brand import current_branch, project_commit
from ...kernel.data import DashboardData, collect_dashboard
from ...kernel.harness_facts import harness_state
from ...kernel.home_snapshot import (
    RECENT_SESSIONS_LIMIT,
    HarnessInstall,
    HomeContext,
    HomeSnapshot,
    ProjectFacts,
    RecentSession,
    RouteStep,
    StoreFacts,
    build_home_snapshot,
)
from ...kernel.reports import LedgerView, load_ledger_view
from ...kernel.repo_map import cached_map, head_commit
from ...kernel.repo_map_settings import memory_status


def project_facts(repo: Path) -> ProjectFacts:
    """The repository name, branch, short HEAD and resolved tracker type; reads no network."""
    try:
        tracker: str = resolve_project_tracker(repo).effective.type
    except Exception:  # an unreadable tracker is shown as unknown, never guessed
        tracker = ""
    return ProjectFacts(
        name=repo.resolve().name,
        branch=current_branch(repo),
        commit=project_commit(repo),
        tracker=tracker,
    )


def harness_install(repo: Path) -> HarnessInstall:
    state = harness_state(repo)
    return HarnessInstall(
        installed=state.installed,
        installed_version=state.installed_version,
        capabilities=len(state.capabilities),
        skills=state.skills,
        managed_files=state.managed_files,
    )


def store_facts(repo: Path) -> StoreFacts:
    """The state authority read from `ledger.json` and the selected generation, without the
    ledger lock and without a runtime call: the runtime store's audit count is not read here."""
    root = repo / STATE_REL
    try:
        pointer = json.loads((root / POINTER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return StoreFacts("none", None, None, None)
    if not isinstance(pointer, dict):
        return StoreFacts("none", None, None, None)
    version = pointer.get("version")
    schema = version if isinstance(version, int) and not isinstance(version, bool) else None
    if schema == STORE_LEDGER_VERSION:
        return StoreFacts("runtime-store", schema, None, None)
    generation = pointer.get("generation")
    records = LifecycleLedger(root).records_root_lenient()
    audit = records / "audit" if records is not None else None
    return StoreFacts(
        authority="file-ledger",
        schema=schema,
        generation=generation if isinstance(generation, str) else None,
        audit_records=(
            sum(1 for _ in audit.glob("*.json"))
            if audit is not None and audit.is_dir()
            else None
        ),
    )


def recent_sessions(view: LedgerView) -> tuple[RecentSession, ...]:
    """The newest batches with the roles and states of their dispatches in dispatch order."""
    sessions: list[RecentSession] = []
    for batch in view.batches[:RECENT_SESSIONS_LIMIT]:
        stages = sorted(
            (stage for stage in view.stages if stage.batch_id == batch.batch_id),
            key=lambda stage: stage.at,
        )
        sessions.append(
            RecentSession(
                batch_id=batch.batch_id,
                ticket=batch.ticket,
                state=batch.state,
                branch=batch.branch,
                created_at=batch.created_at,
                route=tuple(RouteStep(stage.role, stage.state) for stage in stages),
            )
        )
    return tuple(sessions)


def collect_context(repo: Path) -> HomeContext:
    """Read the Repo Map cached for the project's HEAD, the memory status, the project, harness
    and store facts and the recent ledger sessions; builds and writes nothing."""
    head = head_commit(repo)
    try:
        sessions = recent_sessions(load_ledger_view(repo))
    except Exception:  # an unreadable ledger shows no sessions, never stale ones
        sessions = ()
    return HomeContext(
        repo_map=cached_map(repo, head) if head else None,
        memory=memory_status(repo),
        project=project_facts(repo),
        harness=harness_install(repo),
        store=store_facts(repo),
        recent_sessions=sessions,
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
