"""The screen snapshots of Reports, Orchestration, Recovery, Container route, Diagnostics, Harness,
Repo Map, «Открыть проект», «Справка», «Обновить Harness» and «Настройка»: collect them off the
event loop, keep the ledger, the batch history, the health reports, the Harness, the Repo Map, the
«Открыть проект», the «Обновить Harness» and the «Настройка» facts in a short single-flight cache and hand out every snapshot as the
first page of its JSON text, kept for `snapshot.page`."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

from ...kernel.batch_history import History
from ...kernel.help_text import help_sections
from ...kernel.pipeline_kpi import pipeline_analytics, pipeline_kpi, reports_kpi
from ...kernel.pipeline_stats import pipeline_usage
from ...kernel.publish_view import GitFacts, LocalGit, publish_payload
from ...kernel.reports import LedgerView, ledger_payload, timeline_payload
from ...kernel.screen_views import recovery_view_payload, route_view_payload
from ...kernel.update_harness_snapshot import diff_paths
from ..domain.snapshots import HOME_TTL_SECONDS, TextPages
from ....json_types import JsonObject
from .ports import (
    Clock,
    ConfigurationCollector,
    HarnessCollector,
    HealthCollector,
    LedgerCollector,
    LockReader,
    MaintenanceCollector,
    OpenProjectCollector,
    RecoveryReader,
    RepoMapCollector,
    RouteReader,
    UpdateDiffReader,
    UpdateHarnessCollector,
)
from .task_board import TaskBoardService

T = TypeVar("T")


class NotFound(LookupError):
    """The ledger has no report or batch with the requested id."""


@dataclass(frozen=True)
class Paged:
    """The first page of a snapshot's JSON text, the id its other pages are read under and, for
    a cached source, whether it came from the cache and how old it is."""

    snapshot_id: int
    text: str
    next: int
    done: bool
    cached: bool = False
    age_seconds: float = 0.0


@dataclass(frozen=True)
class _Ledger:
    view: LedgerView
    payload: dict[str, object]


class _Source(Generic[T]):
    """One cached value: fresh for the TTL, rebuilt one collect at a time off the loop. The value
    is released when its TTL expires and before every rebuild, so at most one is ever held. A
    failed collect raises and leaves the cache empty; a cancelled waiter never cancels a collect."""

    def __init__(self, ttl: float, clock: Clock) -> None:
        self._ttl = ttl
        self._clock = clock
        self._value: T | None = None
        self._stamp = 0.0
        self._generation = 0
        self._building: asyncio.Task[tuple[T, bool, float]] | None = None

    def _fresh(self) -> tuple[T, bool, float] | None:
        if self._value is None:
            return None
        age = self._clock() - self._stamp
        if age < self._ttl:
            return self._value, True, age
        self._value = None
        return None

    def _release(self, generation: int) -> None:
        if self._generation == generation:
            self._value = None

    async def _rebuild(self, collect: Callable[[], T]) -> tuple[T, bool, float]:
        self._value = None
        try:
            value = await asyncio.to_thread(collect)
            self._value, self._stamp = value, self._clock()
            self._generation += 1
            asyncio.get_running_loop().call_later(
                self._ttl, self._release, self._generation
            )
            return value, False, 0.0
        finally:
            self._building = None

    async def get(
        self, collect: Callable[[], T], *, force: bool = False
    ) -> tuple[T, bool, float]:
        """The value with whether it was cached and its age."""
        while True:
            if not force and (fresh := self._fresh()) is not None:
                return fresh
            if self._building is None:
                break
            await asyncio.wait({self._building})
        task = self._building = asyncio.create_task(self._rebuild(collect))
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        await asyncio.wait({task})
        return task.result()


def snapshot_text(payload: object) -> str:
    """The canonical JSON text of a snapshot payload, as the pages carry it."""
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _ledger(view: LedgerView, git: GitFacts) -> _Ledger:
    """The view with its payload: the ledger without report bodies, the Reports KPIs, which the
    server reads from the whole bodies, and the read-only publication view."""
    payload = {
        **ledger_payload(view),
        "reports_kpi": reports_kpi(view).to_payload(),
        "publish": publish_payload(view, git),
    }
    return _Ledger(view, payload)


class ScreenService:
    """Serves the screen snapshots of one project."""

    def __init__(
        self,
        repo: Path,
        *,
        ttl: float = HOME_TTL_SECONDS,
        clock: Clock,
        ledger: LedgerCollector,
        ledger_online: LedgerCollector,
        lock: LockReader,
        recovery: RecoveryReader,
        route: RouteReader,
        health: HealthCollector | None = None,
        harness: HarnessCollector | None = None,
        maintenance: MaintenanceCollector | None = None,
        repo_map: RepoMapCollector | None = None,
        open_project: OpenProjectCollector | None = None,
        update_harness: UpdateHarnessCollector | None = None,
        update_diff: UpdateDiffReader | None = None,
        configuration: ConfigurationCollector | None = None,
        board: TaskBoardService | None = None,
        publish_git: GitFacts | None = None,
    ) -> None:
        self._repo = repo
        self._git: GitFacts = publish_git or LocalGit(repo)
        self._collect_ledger = ledger
        self._collect_online = ledger_online
        self._read_lock = lock
        self._recovery = recovery
        self._route = route
        self._collect_health = health
        self._collect_harness = harness
        self._collect_maintenance = maintenance
        self._collect_repo_map = repo_map
        self._collect_open_project = open_project
        self._collect_update_harness = update_harness
        self._read_update_diff = update_diff
        self._collect_configuration = configuration
        self._board = board
        self._ledger: _Source[_Ledger] = _Source(ttl, clock)
        self._history: _Source[History] = _Source(ttl, clock)
        # The offline and the online report are separate checks; one never answers for the other.
        self._health: dict[bool, _Source[JsonObject]] = {
            False: _Source(ttl, clock),
            True: _Source(ttl, clock),
        }
        self._harness: _Source[dict[str, object]] = _Source(ttl, clock)
        self._maintenance: _Source[dict[str, object]] = _Source(ttl, clock)
        self._repo_map: _Source[dict[str, object]] = _Source(ttl, clock)
        self._open_project: _Source[dict[str, object]] = _Source(ttl, clock)
        self._update_harness: _Source[dict[str, object]] = _Source(ttl, clock)
        self._configuration: _Source[dict[str, object]] = _Source(ttl, clock)
        self._pages = TextPages()

    async def _paged(
        self, payload: object, cached: bool = False, age: float = 0.0
    ) -> Paged:
        text = await asyncio.to_thread(snapshot_text, payload)
        snapshot_id = self._pages.keep(text)
        page, next_offset, done = self._pages.page(snapshot_id, 0)
        return Paged(snapshot_id, page, next_offset, done, cached, round(age, 3))

    async def _cached_ledger(self, force: bool) -> tuple[_Ledger, bool, float]:
        return await self._ledger.get(
            lambda: _ledger(self._collect_ledger(self._repo), self._git), force=force
        )

    async def reports(self, *, force: bool = False, online: bool = False) -> Paged:
        """The ledger without report bodies; `online` adds the PR timings, always rebuilt and
        never cached."""
        if online:
            found = await asyncio.to_thread(
                lambda: _ledger(self._collect_online(self._repo), self._git)
            )
            return await self._paged(found.payload)
        ledger, cached, age = await self._cached_ledger(force)
        return await self._paged(ledger.payload, cached, age)

    async def report(self, dispatch_id: str) -> Paged:
        """The whole body of one completion report; `NotFound` when the ledger has none."""
        ledger, _, _ = await self._cached_ledger(False)
        for entry in ledger.view.reports:
            if entry.dispatch_id == dispatch_id:
                return await self._paged(entry.report)
        raise NotFound(dispatch_id)

    async def timeline(self, batch_id: str) -> Paged:
        """The chronology of one batch; `NotFound` when the ledger has no such batch."""
        ledger, _, _ = await self._cached_ledger(False)
        timeline = await asyncio.to_thread(ledger.view.timeline, batch_id)
        if timeline is None:
            raise NotFound(batch_id)
        return await self._paged(timeline_payload(timeline))

    async def lock(self) -> dict[str, object]:
        """The ledger lock state, or the text of why it cannot be read."""
        try:
            state = await asyncio.to_thread(self._read_lock, self._repo)
        except Exception as exc:  # shown to the operator, never hidden
            return {"lock": None, "error": str(exc) or type(exc).__name__}
        return {"lock": state, "error": None}

    async def orchestration(self, *, force: bool = False) -> Paged:
        """The ledger of the Orchestration screen with the ledger lock state and the pipeline
        KPIs computed from that ledger."""
        ledger, cached, age = await self._cached_ledger(force)
        lock = await self.lock()
        kpi = await asyncio.to_thread(pipeline_kpi, ledger.view)
        analytics = await asyncio.to_thread(pipeline_analytics, ledger.view)
        return await self._paged(
            {
                "ledger": ledger.payload,
                "lock": lock,
                "kpi": kpi.to_payload(),
                "analytics": analytics.to_payload(),
            },
            cached,
            age,
        )

    async def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> Paged:
        """The batch history and, for a selected batch, its `recovery status`."""
        history, cached, age = await self._history.get(
            lambda: self._recovery.history(self._repo), force=force
        )
        status = (
            await asyncio.to_thread(self._recovery.status, self._repo, batch, skip)
            if batch
            else None
        )
        return await self._paged(
            {
                "history": history.to_payload(),
                "status": status.to_payload() if status is not None else None,
            },
            cached,
            age,
        )

    async def recovery_view(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> Paged:
        """The Recovery screen as the kernel view-models draw it: the history with its labels,
        the recovery gate, the view and the resume plan of the selected batch, from the same
        history cache and `recovery status` reader as `recovery`."""
        history, cached, age = await self._history.get(
            lambda: self._recovery.history(self._repo), force=force
        )
        status = (
            await asyncio.to_thread(self._recovery.status, self._repo, batch, skip)
            if batch
            else None
        )
        payload = await asyncio.to_thread(
            recovery_view_payload, history, status, batch, skip
        )
        return await self._paged(payload, cached, age)

    async def container_route_view(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> Paged:
        """The Container route as the kernel view-models draw it: the selection, the executor
        context, the six stage tabs and every stage view, from the same readers as
        `container_route`; never cached."""
        authored = await asyncio.to_thread(self._route.authored, self._repo)
        preflight = (
            await asyncio.to_thread(
                self._route.preflight, self._repo, batch, role, runtime
            )
            if batch
            else None
        )
        payload = await asyncio.to_thread(
            route_view_payload, authored, preflight, batch, role, runtime
        )
        return await self._paged(payload)

    async def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> Paged:
        """The authored configuration and, for a selected batch, its `dispatch preflight`."""
        authored = await asyncio.to_thread(self._route.authored, self._repo)
        preflight = (
            await asyncio.to_thread(
                self._route.preflight, self._repo, batch, role, runtime
            )
            if batch
            else None
        )
        return await self._paged(
            {
                "authored": authored.to_payload(),
                "preflight": preflight.to_payload() if preflight is not None else None,
            }
        )

    async def diagnostics(self, *, online: bool = False, force: bool = False) -> Paged:
        """The `harness health --json` report, offline or `online`, each cached on its own;
        `NotFound` without a health collector."""
        collect = self._collect_health
        if collect is None:
            raise NotFound("diagnostics")
        report, cached, age = await self._health[online].get(
            lambda: collect(self._repo, online), force=force
        )
        return await self._paged(report, cached, age)

    async def harness(self, *, force: bool = False) -> Paged:
        """The installed harness, the package version and the drift state, with the ledger of
        the pipeline usage from the same cache as Reports and Orchestration; `NotFound`
        without a Harness collector."""
        collect = self._collect_harness
        if collect is None:
            raise NotFound("harness")
        facts, cached, age = await self._harness.get(
            lambda: collect(self._repo), force=force
        )
        ledger, _, _ = await self._cached_ledger(force)
        snapshot = {key: facts[key] for key in ("state", "package_version", "drift")}
        return await self._paged({**snapshot, "ledger": ledger.payload}, cached, age)

    async def harness_overview(self, *, force: bool = False) -> dict[str, object]:
        """The installed harness, the package version, the drift state and the pipeline usage
        counts, from the same Harness and ledger caches as `harness`; `NotFound` without a
        Harness collector."""
        collect = self._collect_harness
        if collect is None:
            raise NotFound("harness")
        facts, cached, age = await self._harness.get(
            lambda: collect(self._repo), force=force
        )
        ledger, _, _ = await self._cached_ledger(force)
        return {
            "state": facts["state"],
            "package_version": facts["package_version"],
            "drift": facts["drift"],
            "drift_files": facts.get("drift_files"),
            "store": facts.get("store"),
            "adapters": facts.get("adapters"),
            "usage": pipeline_usage(ledger.view),
            "cached": cached,
            "age_seconds": round(age, 3),
        }

    async def maintenance(self, *, force: bool = False) -> Paged:
        """The cleanup plans with their sizes and the worktree facts of the Harness screen;
        `NotFound` without a maintenance collector."""
        collect = self._collect_maintenance
        if collect is None:
            raise NotFound("maintenance")
        facts, cached, age = await self._maintenance.get(
            lambda: collect(self._repo), force=force
        )
        return await self._paged(facts, cached, age)

    async def repo_map(self, *, force: bool = False) -> Paged:
        """HEAD, the map cached for it, the tier, the parser bundle, the project languages and
        the memory status of the Repo Map screen; `NotFound` without a Repo Map collector."""
        collect = self._collect_repo_map
        if collect is None:
            raise NotFound("repo_map")
        facts, cached, age = await self._repo_map.get(
            lambda: collect(self._repo), force=force
        )
        return await self._paged(facts, cached, age)

    async def open_project(self, *, force: bool = False) -> Paged:
        """The installation state of the served project and the candidate projects of «Открыть
        проект»; `NotFound` without its collector."""
        collect = self._collect_open_project
        if collect is None:
            raise NotFound("open_project")
        facts, cached, age = await self._open_project.get(
            lambda: collect(self._repo), force=force
        )
        return await self._paged(facts, cached, age)

    async def help(self, language: str) -> Paged:
        """The console guide of «Справка» in `language`, split into its sections."""
        return await self._paged(help_sections(language).to_payload())

    async def _update_facts(
        self, force: bool
    ) -> tuple[dict[str, object], bool, float]:
        collect = self._collect_update_harness
        if collect is None:
            raise NotFound("update_harness")
        return await self._update_harness.get(lambda: collect(self._repo), force=force)

    async def update_harness(self, *, force: bool = False) -> Paged:
        """The installed harness, the package version and the drift report of «Обновить
        Harness»; `NotFound` without its collector."""
        facts, cached, age = await self._update_facts(force)
        return await self._paged(facts, cached, age)

    async def update_diff(self, path: str, *, force: bool = False) -> Paged:
        """The diff of `path` against what `harness update` writes there. Only a file the
        drift report of the same cache lists is read; any other path is `NotFound`, so no
        request reads an arbitrary file."""
        reader = self._read_update_diff
        if reader is None:
            raise NotFound("update_harness.diff")
        facts, _, _ = await self._update_facts(force)
        drift = facts.get("drift")
        listed = diff_paths(drift if isinstance(drift, dict) else None)
        if path not in listed:
            raise NotFound(path)
        text = await asyncio.to_thread(reader, self._repo, path)
        return await self._paged({"path": path, "text": text})

    async def configuration(self, *, force: bool = False) -> Paged:
        """The masked configuration files with their digests, a pending transaction and the
        runtime adapter preview of «Настройка»; `NotFound` without its collector."""
        collect = self._collect_configuration
        if collect is None:
            raise NotFound("configuration")
        facts, cached, age = await self._configuration.get(
            lambda: collect(self._repo), force=force
        )
        return await self._paged(facts, cached, age)

    async def task_board_specs(self, *, force: bool = False) -> Paged:
        """The open specs of the task board; `NotFound` without a configured board."""
        if self._board is None:
            raise NotFound("task_board")
        served = await self._board.specs(force)
        return await self._paged(served.payload, served.cached, served.age_seconds or 0.0)

    async def task_board(self, spec: str, *, force: bool = False) -> Paged:
        """The task board of one spec; `SpecNotFound` when the tracker has no such spec."""
        if self._board is None:
            raise NotFound("task_board")
        served = await self._board.board(spec, force)
        return await self._paged(served.payload, served.cached, served.age_seconds or 0.0)

    def page(self, snapshot_id: int, offset: int) -> tuple[str, int, bool]:
        """A further page of a kept snapshot; `LookupError` when it is no longer kept,
        `ValueError` for an offset beyond its text."""
        return self._pages.page(snapshot_id, offset)
