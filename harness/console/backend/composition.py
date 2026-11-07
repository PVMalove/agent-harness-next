"""The composition root of the console server: the one place that wires the infrastructure
adapters into the use cases."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..kernel.catalog import (
    CONFIGURATION_COMMANDS,
    DIAGNOSTICS_COMMANDS,
    HARNESS_COMMANDS,
    HARNESS_MENU_HIDDEN,
    MEMORY_COMMANDS,
    REPO_MAP_COMMANDS,
    SETUP_COMMANDS,
    UPDATE_SEED_SELECTED,
)
from ..kernel.coordinator_catalog import COORDINATOR_COMMANDS
from harness.orchestration.core.constants import LIVE_DISPATCH_STATES
from .api.request_router import RequestRouter
from .application.decisions import DecisionService
from .application.events import POLL_INTERVAL_SECONDS, OrchestrationEvents
from .application.jobs import JobService
from .application.live_steps import POLL_SECONDS as STEPS_POLL_SECONDS
from .application.live_steps import LiveSteps
from .application.ports import (
    Clock,
    ConfigurationCollector,
    CommandSpec,
    HarnessCollector,
    HealthCollector,
    HomeCollector,
    JobExecutor,
    LedgerCollector,
    LockReader,
    MaintenanceCollector,
    OpenProjectCollector,
    OrchestrationReader,
    RecoveryReader,
    RepoMapCollector,
    RouteReader,
    UpdateDiffReader,
    UpdateHarnessCollector,
)
from .application.screens import ScreenService
from .application.task_board import TaskBoardService
from .application.snapshots import SnapshotService
from .application.worker_steps import POLL_SECONDS, WorkerStepsQuery
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
    HealthFacts,
    collect_ledger,
    collect_ledger_online,
    configuration_facts,
    harness_facts,
    maintenance_facts,
    open_project_facts,
    read_lock,
    repo_map_facts,
    update_diff as read_update_diff,
    update_harness_facts,
)
from .infrastructure.task_board_tracker import TrackerBoardReader
from .infrastructure.worker_steps import read_worker_facts, read_worker_log


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
    health: HealthCollector | None = None,
    harness: HarnessCollector | None = None,
    maintenance: MaintenanceCollector | None = None,
    repo_map: RepoMapCollector | None = None,
    open_project: OpenProjectCollector | None = None,
    update_harness: UpdateHarnessCollector | None = None,
    update_diff: UpdateDiffReader | None = None,
    configuration: ConfigurationCollector | None = None,
    board: TaskBoardService | None = None,
) -> ScreenService:
    """The screen snapshot service; a port left out gets its infrastructure adapter."""
    facts = CoordinatorFacts()
    clock = monotonic if clock is None else clock
    ledger = collect_ledger if ledger is None else ledger
    return ScreenService(
        repo,
        ttl=ttl,
        clock=clock,
        ledger=ledger,
        ledger_online=collect_ledger_online if ledger_online is None else ledger_online,
        lock=read_lock if lock is None else lock,
        recovery=facts if recovery is None else recovery,
        route=facts if route is None else route,
        health=HealthFacts() if health is None else health,
        harness=harness_facts if harness is None else harness,
        maintenance=maintenance_facts if maintenance is None else maintenance,
        repo_map=repo_map_facts if repo_map is None else repo_map,
        open_project=open_project_facts if open_project is None else open_project,
        update_harness=(
            update_harness_facts if update_harness is None else update_harness
        ),
        update_diff=read_update_diff if update_diff is None else update_diff,
        configuration=configuration_facts if configuration is None else configuration,
        board=(
            TaskBoardService(
                repo, clock=clock, reader=TrackerBoardReader(), ledger=ledger
            )
            if board is None
            else board
        ),
    )


def job_service(repo: Path, *, executor: JobExecutor | None = None) -> JobService:
    """The job service over the harness, the selected seed update, Diagnostics, Repo Map,
    installation, configuration, memory, coordinator and native permission commands; without
    `executor` the commands run as subprocesses."""
    entries: tuple[CommandSpec, ...] = (
        *HARNESS_COMMANDS,
        UPDATE_SEED_SELECTED,
        *DIAGNOSTICS_COMMANDS,
        *REPO_MAP_COMMANDS,
        *SETUP_COMMANDS,
        *CONFIGURATION_COMMANDS,
        *MEMORY_COMMANDS,
        *COORDINATOR_COMMANDS,
        *NATIVE_PERMISSION_COMMANDS,
    )
    listed = {
        "harness": tuple(
            entry for entry in HARNESS_COMMANDS if entry.key not in HARNESS_MENU_HIDDEN
        ),
        "diagnostics": DIAGNOSTICS_COMMANDS,
        "repo-map": REPO_MAP_COMMANDS,
        "setup": SETUP_COMMANDS,
        "configuration": CONFIGURATION_COMMANDS,
        "memory": MEMORY_COMMANDS,
        "decisions": tuple(
            entry for entry in COORDINATOR_COMMANDS
            if entry.key in {"batch-approve", "batch-decide", "batch-attention-resolve", "dispatch-propose", "dispatch-create"}
        ) + NATIVE_PERMISSION_COMMANDS,
    }
    return JobService(
        repo,
        catalog={entry.key: entry for entry in entries},
        sections={
            entry.key: section for section, group in listed.items() for entry in group
        },
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


def worker_steps_query(
    repo: Path, *, poll_seconds: float = POLL_SECONDS
) -> WorkerStepsQuery:
    """Worker steps read from the project's ledger records and worker logs, without the lock."""
    return WorkerStepsQuery(
        repo,
        facts=read_worker_facts,
        log=read_worker_log,
        poll_seconds=poll_seconds,
    )


def live_steps(
    events: OrchestrationEvents,
    workers: WorkerStepsQuery,
    *,
    poll_seconds: float = STEPS_POLL_SECONDS,
) -> LiveSteps:
    """The live step feed over the server's event journal and worker logs; it follows the
    dispatches in the coordinator's live states."""
    return LiveSteps(
        events,
        workers,
        now=utc_now_iso,
        live_states={state.value for state in LIVE_DISPATCH_STATES},
        poll_seconds=poll_seconds,
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
    workers: WorkerStepsQuery
    steps: LiveSteps
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
    workers: WorkerStepsQuery | None = None,
    steps: LiveSteps | None = None,
) -> Composition:
    """The services of one console server, with the given ones kept, and its request router."""
    snapshots = snapshots or snapshot_service(repo)
    jobs = jobs or job_service(repo)
    decisions = decisions or decision_service(repo)
    events = events or orchestration_events(repo)
    screens = screens or screen_service(repo)
    workers = workers or worker_steps_query(repo)
    steps = steps or live_steps(events, workers)
    return Composition(
        snapshots,
        jobs,
        decisions,
        events,
        screens,
        workers,
        steps,
        RequestRouter(snapshots, jobs, decisions, events, screens, workers, steps),
        Discovery,
    )
