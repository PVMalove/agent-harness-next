"""The composition root of the console server: the one place that wires the infrastructure
adapters into the use cases."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..kernel.catalog import HARNESS_COMMANDS, MEMORY_COMMANDS
from ..kernel.coordinator_catalog import COORDINATOR_COMMANDS
from .api.request_router import RequestRouter
from .application.decisions import DecisionService
from .application.events import POLL_INTERVAL_SECONDS, OrchestrationEvents
from .application.jobs import JobService
from .application.ports import (
    Clock,
    CommandSpec,
    HomeCollector,
    JobExecutor,
    LedgerCollector,
    LockReader,
    OrchestrationReader,
    RecoveryReader,
    RouteReader,
)
from .application.screens import ScreenService
from .application.snapshots import SnapshotService
from .domain.approvals import DecisionsSnapshot
from .domain.snapshots import HOME_TTL_SECONDS
from .infrastructure import command_journal
from .infrastructure.clock import monotonic, utc_now_iso
from .infrastructure.discovery import Discovery
from .infrastructure.event_journal import opener
from .infrastructure.home_facts import collect_home
from .infrastructure.ids import new_id
from .infrastructure.ledger import collect_decisions
from .infrastructure.native_permission import NATIVE_PERMISSION_COMMANDS
from .infrastructure.orchestration_reader import ProjectReader
from .infrastructure.processes import run_command
from .infrastructure.screen_facts import (
    CoordinatorFacts,
    collect_ledger,
    collect_ledger_online,
    read_lock,
)


def snapshot_service(
    repo: Path,
    *,
    ttl: float = HOME_TTL_SECONDS,
    clock: Clock | None = None,
    collect: HomeCollector | None = None,
    collect_online: HomeCollector | None = None,
) -> SnapshotService:
    """The Home snapshot service; a port left out gets its infrastructure adapter."""
    return SnapshotService(
        repo,
        ttl=ttl,
        clock=monotonic if clock is None else clock,
        collect=collect_home if collect is None else collect,
        collect_online=(
            functools.partial(collect_home, online=True)
            if collect_online is None
            else collect_online
        ),
    )


def screen_service(
    repo: Path,
    *,
    ttl: float = HOME_TTL_SECONDS,
    clock: Clock | None = None,
    ledger: LedgerCollector | None = None,
    ledger_online: LedgerCollector | None = None,
    lock: LockReader | None = None,
    recovery: RecoveryReader | None = None,
    route: RouteReader | None = None,
) -> ScreenService:
    """The screen snapshot service; a port left out gets its infrastructure adapter."""
    facts = CoordinatorFacts()
    return ScreenService(
        repo,
        ttl=ttl,
        clock=monotonic if clock is None else clock,
        ledger=collect_ledger if ledger is None else ledger,
        ledger_online=collect_ledger_online if ledger_online is None else ledger_online,
        lock=read_lock if lock is None else lock,
        recovery=facts if recovery is None else recovery,
        route=facts if route is None else route,
    )


def job_service(repo: Path, *, executor: JobExecutor | None = None) -> JobService:
    """The job service over the harness, memory, coordinator and native permission commands;
    without `executor` the commands run as subprocesses."""
    entries: tuple[CommandSpec, ...] = (
        *HARNESS_COMMANDS,
        *MEMORY_COMMANDS,
        *COORDINATOR_COMMANDS,
        *NATIVE_PERMISSION_COMMANDS,
    )
    return JobService(
        repo,
        catalog={entry.key: entry for entry in entries},
        executor=run_command if executor is None else executor,
        journal=command_journal.append,
        new_id=new_id,
        now=utc_now_iso,
    )


def decision_service(
    repo: Path, *, collect: Callable[[Path], DecisionsSnapshot] | None = None
) -> DecisionService:
    """The pending decisions service; without `collect` it reads the project's ledger."""
    return DecisionService(
        repo, collect=collect_decisions if collect is None else collect
    )


def orchestration_events(
    repo: Path,
    *,
    reader: OrchestrationReader | None = None,
    interval: float = POLL_INTERVAL_SECONDS,
    journal_path: Path | None = None,
) -> OrchestrationEvents:
    """The orchestration events of the project; without `reader` it reads the project's ledger
    or runtime store, and without `journal_path` the journal lies beside the discovery record."""
    root = repo.resolve()
    return OrchestrationEvents(
        root,
        reader=ProjectReader(root) if reader is None else reader,
        open_journal=opener(root, journal_path),
        now=utc_now_iso,
        interval=interval,
    )


@dataclass(frozen=True)
class Composition:
    """Everything one console server is built from. `discovery` makes the project's discovery
    owner when the server starts."""

    snapshots: SnapshotService
    jobs: JobService
    decisions: DecisionService
    events: OrchestrationEvents
    screens: ScreenService
    router: RequestRouter
    discovery: Callable[[Path], Discovery]


def compose(
    repo: Path,
    *,
    snapshots: SnapshotService | None = None,
    jobs: JobService | None = None,
    decisions: DecisionService | None = None,
    events: OrchestrationEvents | None = None,
    screens: ScreenService | None = None,
) -> Composition:
    """The services of one console server, with the given ones kept, and its request router."""
    snapshots = snapshots or snapshot_service(repo)
    jobs = jobs or job_service(repo)
    decisions = decisions or decision_service(repo)
    events = events or orchestration_events(repo)
    screens = screens or screen_service(repo)
    return Composition(
        snapshots,
        jobs,
        decisions,
        events,
        screens,
        RequestRouter(snapshots, jobs, decisions, events, screens),
        Discovery,
    )
