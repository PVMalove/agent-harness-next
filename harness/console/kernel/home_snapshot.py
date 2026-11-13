"""The Home snapshot model shared by the server and the TUI client: standard library only.

`build_home_snapshot` is the one mapping from the dashboard data and the Home context to JSON-safe
values; the Home screen of the TUI shows the same facts. `HomeSnapshot.to_payload` and
`HomeSnapshot.from_payload` are the wire codec of a `home.snapshot` reply. Nothing here imports
`rich`, `textual`, `h11` or `websockets`."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from typing import TypeVar

from .data import DashboardData
from .protocol import ID_BYTES, MESSAGE_BYTES, _clip
from .repo_map import RepoMapView
from .repo_map_settings import MemoryStatus

SCHEMA_VERSION = 2

PROBLEMS_LIMIT = 100
SOURCE_TYPES_LIMIT = 32
AREAS_LIMIT = 64
RECENT_SESSIONS_LIMIT = 3
ROUTE_LIMIT = 16

_TIER = re.compile(r"tier=(\w+)")


@dataclass(frozen=True)
class HomeContext:
    """What the context cards show beside the health facts: the Repo Map cached for HEAD and the
    state of project memory. Either is None when the console cannot read it."""

    repo_map: RepoMapView | None = None
    memory: MemoryStatus | None = None
    project: ProjectFacts | None = None
    harness: HarnessInstall | None = None
    store: StoreFacts | None = None
    recent_sessions: tuple[RecentSession, ...] = ()
    # The latest cached map of another commit when HEAD has none ("stale for HEAD").
    stale_map: RepoMapView | None = None


@dataclass(frozen=True)
class HealthCounters:
    ok: int
    warn: int
    fail: int
    skipped: int


@dataclass(frozen=True)
class Problem:
    status: str
    id: str
    message: str
    # The health area (`CheckResult.group`) of the check; "" when it is unknown.
    group: str = ""


@dataclass(frozen=True)
class ProjectFacts:
    """The repository the console is pointed at: its name, checked-out branch, short HEAD and the
    resolved tracker type. A fact that cannot be read is None (tracker: "")."""

    name: str
    branch: str | None
    commit: str | None
    tracker: str


@dataclass(frozen=True)
class HarnessInstall:
    """What `.harness/harness.lock` and the skills directory say is installed."""

    installed: bool
    installed_version: str
    capabilities: int
    skills: int
    managed_files: int
    # The installed capability names in lock order, and those `harness/CAPABILITIES.json` lacks.
    capability_names: tuple[str, ...] = ()
    uncatalogued: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoreFacts:
    """The authority of the orchestration state: `authority` is "file-ledger", "runtime-store" or
    "none". The generation comes from the `ledger.json` pointer in both epochs; the audit count is
    counted on disk in the file-ledger epoch and asked from the runtime (`state.validate`, never
    starting it) in the runtime-store epoch; `cutover_at` comes from `AUTHORITY.json` and is None
    before a cutover. An unread fact is None and `reason` says why (empty when all were read)."""

    authority: str
    schema: int | None
    generation: str | None
    audit_records: int | None
    cutover_at: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class DriftCounts:
    """The managed-file counts of `harness diff --json`; `total` is every differing file."""

    total: int
    added: int
    missing: int
    package_changed: int
    local_changed: int
    conflict: int
    retired: int


@dataclass(frozen=True)
class AreaCounters:
    """The health check counts of one area (`CheckResult.group`)."""

    area: str
    ok: int
    warn: int
    fail: int
    skipped: int


@dataclass(frozen=True)
class RouteStep:
    """One recorded dispatch of a batch, in dispatch order."""

    role: str
    state: str


@dataclass(frozen=True)
class RecentSession:
    """A recent batch of the ledger with the route of its dispatches."""

    batch_id: str
    ticket: str
    state: str
    branch: str
    created_at: str
    route: tuple[RouteStep, ...]
    # The time of the batch's latest dispatch (its creation when it has none): the Home list shows
    # the duration from `created_at` to it.
    updated_at: str = ""


@dataclass(frozen=True)
class HeadMap:
    """The Repo Map cached for HEAD."""

    origin: str
    commit: str
    files: int
    edges: int
    estimated_tokens: int


@dataclass(frozen=True)
class RepoMapCard:
    tier: str | None
    message: str
    head_map: HeadMap | None  # None: there is no map for HEAD
    # The latest cached map of another commit, shown as stale for HEAD; None with a HEAD map.
    stale_map: HeadMap | None = None


@dataclass(frozen=True)
class MemoryState:
    """The `memory.index` health check."""

    status: str
    message: str


@dataclass(frozen=True)
class MemoryPolicy:
    enabled: bool
    active: bool
    source_types: tuple[str, ...]
    indexed: int | None
    problem: str
    inactive: str
    top_k: int | None
    max_tokens: int | None


@dataclass(frozen=True)
class MemoryCard:
    state: MemoryState | None
    policy: MemoryPolicy | None


@dataclass(frozen=True)
class HomeSnapshot:
    version: int
    health: HealthCounters
    problems: tuple[Problem, ...]
    problems_total: int
    harness_version: str
    drift: str
    active_batches: int | None  # None: orchestration is not connected
    repo_map: RepoMapCard
    memory: MemoryCard
    project: ProjectFacts | None = None
    harness: HarnessInstall | None = None
    store: StoreFacts | None = None
    drift_counts: DriftCounts | None = None  # None: `harness diff --json` could not be read
    areas: tuple[AreaCounters, ...] = ()
    # The skipped checks (bounded by PROBLEMS_LIMIT); they are not part of `problems`.
    skipped_checks: tuple[Problem, ...] = ()
    recent_sessions: tuple[RecentSession, ...] = ()

    def to_payload(self) -> dict[str, object]:
        """The snapshot as one reply carries it: only the `listed_problems`, so that any reply
        stays below the message limit; `problems_total` keeps the real count."""
        payload = asdict(self)
        payload["problems"] = [asdict(problem) for problem in self.listed_problems()]
        return payload

    def listed_problems(self) -> tuple[Problem, ...]:
        """The first `PROBLEMS_LIMIT` problems with their texts clipped. When they are not all of
        `problems`, a client reads the whole list with `home.problems`."""
        return tuple(
            Problem(
                _clip(problem.status, ID_BYTES),
                _clip(problem.id, ID_BYTES),
                _clip(problem.message, MESSAGE_BYTES),
                _clip(problem.group, ID_BYTES),
            )
            for problem in self.problems[:PROBLEMS_LIMIT]
        )

    @classmethod
    def from_payload(cls, payload: object) -> HomeSnapshot:
        """The snapshot a `to_payload` result (read back from JSON) describes. Every field must be
        present with its schema type and nothing else may be there; any mismatch is `ValueError`."""
        found = _fields(payload, cls)
        version = _int(found["version"])
        if version != SCHEMA_VERSION:
            raise ValueError(f"unsupported snapshot version: {version!r}")
        return cls(
            version=version,
            health=_health_from(found["health"]),
            problems=tuple(_problem_from(item) for item in _list(found["problems"])),
            problems_total=_int(found["problems_total"]),
            harness_version=_str(found["harness_version"]),
            drift=_str(found["drift"]),
            active_batches=_optional(found["active_batches"], _int),
            repo_map=_repo_map_from(found["repo_map"]),
            memory=_memory_from(found["memory"]),
            project=_optional(found["project"], _project_from),
            harness=_optional(found["harness"], _harness_from),
            store=_optional(found["store"], _store_from),
            drift_counts=_optional(found["drift_counts"], _drift_counts_from),
            areas=tuple(_area_from(item) for item in _list(found["areas"])),
            skipped_checks=tuple(
                _problem_from(item) for item in _list(found["skipped_checks"])
            ),
            recent_sessions=tuple(
                _session_from(item) for item in _list(found["recent_sessions"])
            ),
        )


_T = TypeVar("_T")


def _fields(payload: object, kind: type) -> dict[str, object]:
    """The object's fields when its keys are exactly those of the dataclass `kind`."""
    if not isinstance(payload, dict):
        raise ValueError(f"{kind.__name__}: not an object")
    if set(payload) != {field.name for field in fields(kind)}:
        raise ValueError(f"{kind.__name__}: fields {sorted(map(str, payload))}")
    return {str(key): value for key, value in payload.items()}


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"not an integer: {value!r}")
    return value


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"not a string: {value!r}")
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"not a boolean: {value!r}")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"not a list: {value!r}")
    return value


def _optional(value: object, parse: Callable[[object], _T]) -> _T | None:
    return None if value is None else parse(value)


def _health_from(value: object) -> HealthCounters:
    found = _fields(value, HealthCounters)
    return HealthCounters(
        ok=_int(found["ok"]),
        warn=_int(found["warn"]),
        fail=_int(found["fail"]),
        skipped=_int(found["skipped"]),
    )


def _problem_from(value: object) -> Problem:
    found = _fields(value, Problem)
    return Problem(
        status=_str(found["status"]),
        id=_str(found["id"]),
        message=_str(found["message"]),
        group=_str(found["group"]),
    )


def _project_from(value: object) -> ProjectFacts:
    found = _fields(value, ProjectFacts)
    return ProjectFacts(
        name=_str(found["name"]),
        branch=_optional(found["branch"], _str),
        commit=_optional(found["commit"], _str),
        tracker=_str(found["tracker"]),
    )


def _harness_from(value: object) -> HarnessInstall:
    found = _fields(value, HarnessInstall)
    return HarnessInstall(
        installed=_bool(found["installed"]),
        installed_version=_str(found["installed_version"]),
        capabilities=_int(found["capabilities"]),
        skills=_int(found["skills"]),
        managed_files=_int(found["managed_files"]),
        capability_names=tuple(_str(item) for item in _list(found["capability_names"])),
        uncatalogued=tuple(_str(item) for item in _list(found["uncatalogued"])),
    )


def store_from_payload(value: object) -> StoreFacts:
    """The `StoreFacts` of their JSON object; anything off the schema is a `ValueError`."""
    return _store_from(value)


def _store_from(value: object) -> StoreFacts:
    found = _fields(value, StoreFacts)
    return StoreFacts(
        authority=_str(found["authority"]),
        schema=_optional(found["schema"], _int),
        generation=_optional(found["generation"], _str),
        audit_records=_optional(found["audit_records"], _int),
        cutover_at=_optional(found["cutover_at"], _str),
        reason=_str(found["reason"]),
    )


def _drift_counts_from(value: object) -> DriftCounts:
    found = _fields(value, DriftCounts)
    return DriftCounts(**{name: _int(found[name]) for name in found})


def _area_from(value: object) -> AreaCounters:
    found = _fields(value, AreaCounters)
    return AreaCounters(
        area=_str(found["area"]),
        ok=_int(found["ok"]),
        warn=_int(found["warn"]),
        fail=_int(found["fail"]),
        skipped=_int(found["skipped"]),
    )


def _route_step_from(value: object) -> RouteStep:
    found = _fields(value, RouteStep)
    return RouteStep(role=_str(found["role"]), state=_str(found["state"]))


def _session_from(value: object) -> RecentSession:
    found = _fields(value, RecentSession)
    return RecentSession(
        batch_id=_str(found["batch_id"]),
        ticket=_str(found["ticket"]),
        state=_str(found["state"]),
        branch=_str(found["branch"]),
        created_at=_str(found["created_at"]),
        route=tuple(_route_step_from(item) for item in _list(found["route"])),
        updated_at=_str(found["updated_at"]),
    )


def problems_text(problems: tuple[Problem, ...]) -> str:
    """The problems as the JSON text `home.problems` pages through."""
    return json.dumps(
        [asdict(problem) for problem in problems],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def problems_from_text(text: str) -> tuple[Problem, ...]:
    """The problems a `problems_text` result describes; any mismatch is `ValueError`."""
    try:
        items = json.loads(text)
    except RecursionError:
        raise ValueError("problems: too deeply nested") from None
    return tuple(_problem_from(item) for item in _list(items))


def _head_map_from(value: object) -> HeadMap:
    found = _fields(value, HeadMap)
    return HeadMap(
        origin=_str(found["origin"]),
        commit=_str(found["commit"]),
        files=_int(found["files"]),
        edges=_int(found["edges"]),
        estimated_tokens=_int(found["estimated_tokens"]),
    )


def _repo_map_from(value: object) -> RepoMapCard:
    found = _fields(value, RepoMapCard)
    return RepoMapCard(
        tier=_optional(found["tier"], _str),
        message=_str(found["message"]),
        head_map=_optional(found["head_map"], _head_map_from),
        stale_map=_optional(found["stale_map"], _head_map_from),
    )


def _memory_state_from(value: object) -> MemoryState:
    found = _fields(value, MemoryState)
    return MemoryState(status=_str(found["status"]), message=_str(found["message"]))


def _memory_policy_from(value: object) -> MemoryPolicy:
    found = _fields(value, MemoryPolicy)
    return MemoryPolicy(
        enabled=_bool(found["enabled"]),
        active=_bool(found["active"]),
        source_types=tuple(_str(item) for item in _list(found["source_types"])),
        indexed=_optional(found["indexed"], _int),
        problem=_str(found["problem"]),
        inactive=_str(found["inactive"]),
        top_k=_optional(found["top_k"], _int),
        max_tokens=_optional(found["max_tokens"], _int),
    )


def _memory_from(value: object) -> MemoryCard:
    found = _fields(value, MemoryCard)
    return MemoryCard(
        state=_optional(found["state"], _memory_state_from),
        policy=_optional(found["policy"], _memory_policy_from),
    )


def _head_map(view: RepoMapView | None) -> HeadMap | None:
    if view is None:
        return None
    return HeadMap(
        origin=_clip(view.origin, ID_BYTES),
        commit=_clip(view.commit, ID_BYTES),
        files=len(view.files),
        edges=len(view.edges),
        estimated_tokens=view.estimated_tokens,
    )


def _repo_map_card(
    data: DashboardData, view: RepoMapView | None, stale: RepoMapView | None = None
) -> RepoMapCard:
    found = _TIER.search(data.repo_map_tier)
    tier = found.group(1) if found else (view.tier if view is not None else None)
    return RepoMapCard(
        tier,
        _clip(data.repo_map_tier, MESSAGE_BYTES),
        _head_map(view),
        _head_map(stale) if view is None else None,
    )


def _memory_card(data: DashboardData, status: MemoryStatus | None) -> MemoryCard:
    check = data.memory_index
    return MemoryCard(
        state=MemoryState(
            _clip(check.status, ID_BYTES), _clip(check.message, MESSAGE_BYTES)
        )
        if check is not None
        else None,
        policy=MemoryPolicy(
            enabled=status.enabled,
            active=status.active,
            source_types=tuple(
                _clip(name, ID_BYTES)
                for name in status.source_types[:SOURCE_TYPES_LIMIT]
            ),
            indexed=status.indexed,
            problem=_clip(status.problem, MESSAGE_BYTES),
            inactive=_clip(status.inactive, MESSAGE_BYTES),
            top_k=status.top_k,
            max_tokens=status.max_tokens,
        )
        if status is not None
        else None,
    )


_AREA_STATUSES = ("ok", "warn", "fail", "skipped")


def _areas(data: DashboardData) -> tuple[AreaCounters, ...]:
    """The check counts per area, in the order the areas first appear in the report."""
    counts: dict[str, dict[str, int]] = {}
    for status, _check_id, _message, group in data.checks:
        area = counts.setdefault(group, dict.fromkeys(_AREA_STATUSES, 0))
        if status in area:
            area[status] += 1
    return tuple(
        AreaCounters(_clip(name, ID_BYTES), **found)
        for name, found in list(counts.items())[:AREAS_LIMIT]
    )


def _skipped(data: DashboardData) -> tuple[Problem, ...]:
    return tuple(
        Problem(
            _clip(status, ID_BYTES),
            _clip(check_id, ID_BYTES),
            _clip(message, MESSAGE_BYTES),
            _clip(group, ID_BYTES),
        )
        for status, check_id, message, group in data.checks
        if status == "skipped"
    )[:PROBLEMS_LIMIT]


def _drift_counts(data: DashboardData) -> DriftCounts | None:
    if data.drift_counts is None:
        return None
    found = dict(data.drift_counts)
    names = [field.name for field in fields(DriftCounts) if field.name != "total"]
    values = {name: max(0, found.get(name, 0)) for name in names}
    return DriftCounts(total=sum(values.values()), **values)


def _bounded_sessions(
    sessions: tuple[RecentSession, ...],
) -> tuple[RecentSession, ...]:
    return tuple(
        RecentSession(
            batch_id=_clip(session.batch_id, ID_BYTES),
            ticket=_clip(session.ticket, ID_BYTES),
            state=_clip(session.state, ID_BYTES),
            branch=_clip(session.branch, ID_BYTES),
            created_at=_clip(session.created_at, ID_BYTES),
            route=tuple(
                RouteStep(_clip(step.role, ID_BYTES), _clip(step.state, ID_BYTES))
                for step in session.route[-ROUTE_LIMIT:]
            ),
            updated_at=_clip(session.updated_at, ID_BYTES),
        )
        for session in sessions[:RECENT_SESSIONS_LIMIT]
    )


def build_home_snapshot(data: DashboardData, context: HomeContext) -> HomeSnapshot:
    """Map the dashboard data and the Home context to JSON-safe values. The problems stay whole,
    as the Home screen shows them; `to_payload` bounds what one reply lists."""
    groups = {check_id: group for _status, check_id, _message, group in data.checks}
    project = context.project
    return HomeSnapshot(
        version=SCHEMA_VERSION,
        health=HealthCounters(data.ok, data.warn, data.fail, data.skipped),
        problems=tuple(
            Problem(status, check_id, message, groups.get(check_id, ""))
            for status, check_id, message in data.problems
        ),
        problems_total=len(data.problems),
        harness_version=_clip(data.harness_version, ID_BYTES),
        drift=_clip(data.drift_state, ID_BYTES),
        active_batches=data.active_batches,
        repo_map=_repo_map_card(data, context.repo_map, context.stale_map),
        memory=_memory_card(data, context.memory),
        project=ProjectFacts(
            _clip(project.name, ID_BYTES),
            _clip(project.branch, ID_BYTES) if project.branch is not None else None,
            _clip(project.commit, ID_BYTES) if project.commit is not None else None,
            _clip(project.tracker, ID_BYTES),
        )
        if project is not None
        else None,
        harness=context.harness,
        store=context.store,
        drift_counts=_drift_counts(data),
        areas=_areas(data),
        skipped_checks=_skipped(data),
        recent_sessions=_bounded_sessions(context.recent_sessions),
    )
