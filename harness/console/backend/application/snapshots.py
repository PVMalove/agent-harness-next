"""Typed console facts for clients that cannot import the TUI: standard library only.

`build_home_snapshot` is the one mapping from the dashboard data and the Home context to JSON-safe
values; the Home screen of the TUI shows the same facts. Nothing here imports `rich`, `textual`,
`h11` or `websockets`."""

from __future__ import annotations

import asyncio
import functools
import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Protocol, TypeVar, cast

from ...kernel.data import DashboardData, collect_dashboard
from ...kernel.repo_map import RepoMapView, cached_map, head_commit
from ...kernel.repo_map_settings import MemoryStatus, memory_status

SCHEMA_VERSION = 1
HOME_TTL_SECONDS = 15.0

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 4096
MAX_ID_CHARS = 64
HOME_REQUEST = "home.snapshot"
HOME_PROBLEMS_REQUEST = "home.problems"

PROBLEMS_LIMIT = 100
SOURCE_TYPES_LIMIT = 32
MESSAGE_BYTES = 300
ID_BYTES = 100
# A `home.problems` page: the problems beyond what one Home reply lists, in wire bytes.
PAGE_BYTES = 32768
# How many rebuilt snapshots keep their problems for paging. The cached snapshot is never
# evicted while it is cached, so a Home reply that hands it out can always be paged.
KEPT_SNAPSHOTS = 4

_TIER = re.compile(r"tier=(\w+)")


@dataclass(frozen=True)
class HomeContext:
    """What the context cards show beside the health facts: the Repo Map cached for HEAD and the
    state of project memory. Either is None when the console cannot read it."""

    repo_map: RepoMapView | None = None
    memory: MemoryStatus | None = None


def collect_context(repo: Path) -> HomeContext:
    """Read the Repo Map cached for the project's HEAD and the memory status; builds nothing."""
    head = head_commit(repo)
    return HomeContext(
        repo_map=cached_map(repo, head) if head else None, memory=memory_status(repo)
    )


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


_SHORT_ESCAPES = frozenset('"\\\b\f\n\r\t')
# json.loads accepts "\ud800"; the str cannot be encoded as UTF-8, so a reply carries it escaped.
_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _wire_cost(char: str) -> int:
    """Bytes `char` takes inside a JSON string: a quote, a backslash or a short escape is two,
    any other control character and a lone surrogate (sent as `\\udXXX`) is six, everything
    else is its UTF-8 length."""
    if char in _SHORT_ESCAPES:
        return 2
    if char < " " or _LONE_SURROGATE.match(char):
        return 6
    return len(char.encode("utf-8"))


def _clip(text: str, limit: int) -> str:
    """The longest prefix of `text` that takes at most `limit` bytes as a JSON string."""
    used = 0
    for index, char in enumerate(text[:limit]):
        used += _wire_cost(char)
        if used > limit:
            return text[:index]
    return text[:limit]


def _repo_map_card(data: DashboardData, view: RepoMapView | None) -> RepoMapCard:
    found = _TIER.search(data.repo_map_tier)
    tier = found.group(1) if found else (view.tier if view is not None else None)
    head_map = (
        HeadMap(
            origin=_clip(view.origin, ID_BYTES),
            commit=_clip(view.commit, ID_BYTES),
            files=len(view.files),
            edges=len(view.edges),
            estimated_tokens=view.estimated_tokens,
        )
        if view is not None
        else None
    )
    return RepoMapCard(tier, _clip(data.repo_map_tier, MESSAGE_BYTES), head_map)


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


def build_home_snapshot(data: DashboardData, context: HomeContext) -> HomeSnapshot:
    """Map the dashboard data and the Home context to JSON-safe values. The problems stay whole,
    as the Home screen shows them; `to_payload` bounds what one reply lists."""
    return HomeSnapshot(
        version=SCHEMA_VERSION,
        health=HealthCounters(data.ok, data.warn, data.fail, data.skipped),
        problems=tuple(
            Problem(status, check_id, message)
            for status, check_id, message in data.problems
        ),
        problems_total=len(data.problems),
        harness_version=_clip(data.harness_version, ID_BYTES),
        drift=_clip(data.drift_state, ID_BYTES),
        active_batches=data.active_batches,
        repo_map=_repo_map_card(data, context.repo_map),
        memory=_memory_card(data, context.memory),
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


@dataclass(frozen=True)
class Served:
    """A snapshot as served: whether it came from the cache, how old it is and the id under
    which its problems are paged."""

    snapshot: HomeSnapshot
    cached: bool
    age_seconds: float
    snapshot_id: int


class SnapshotService:
    """Serves the Home snapshot from a short cache so that the expensive checks (health, drift)
    do not rerun on every request. One rebuild runs at a time and never on the event loop."""

    def __init__(
        self,
        repo: Path,
        *,
        ttl: float = HOME_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        collect: Callable[[Path], HomeSnapshot] = collect_home,
        collect_online: Callable[[Path], HomeSnapshot] = functools.partial(
            collect_home, online=True
        ),
    ) -> None:
        self._repo = repo
        self._ttl = ttl
        self._clock = clock
        self._collect = collect
        self._collect_online = collect_online
        self._building: asyncio.Task[Served] | None = None
        self._snapshot: HomeSnapshot | None = None
        self._snapshot_id = 0
        self._stamp = 0.0
        self._kept: dict[int, HomeSnapshot] = {}
        self._last_id = 0

    def _fresh(self) -> Served | None:
        if self._snapshot is None:
            return None
        age = self._clock() - self._stamp
        if age >= self._ttl:
            return None
        return Served(self._snapshot, True, age, self._snapshot_id)

    def _keep(self, snapshot: HomeSnapshot) -> int:
        """Keep a rebuilt snapshot for `problems_page`; beyond the limit the oldest goes, but
        never the cached one, which the service still hands out."""
        self._last_id += 1
        self._kept[self._last_id] = snapshot
        while len(self._kept) > KEPT_SNAPSHOTS:
            del self._kept[next(key for key in self._kept if key != self._snapshot_id)]
        return self._last_id

    async def _rebuild(self) -> Served:
        """The collect, as a task of its own: it records its result and ends the rebuild even
        when every request that waited for it was cancelled."""
        try:
            snapshot = await asyncio.to_thread(self._collect, self._repo)
            snapshot_id = self._keep(snapshot)
            self._snapshot, self._stamp = snapshot, self._clock()
            self._snapshot_id = snapshot_id
            return Served(snapshot, False, 0.0, snapshot_id)
        finally:
            self._building = None

    async def home(self, *, force: bool = False) -> Served:
        """The cached snapshot while it is younger than the TTL, else a rebuilt one. `force`
        always rebuilds. A failed collect raises and leaves the cache as it was. A request that
        is cancelled while it waits does not cancel the collect: the next one waits for it."""
        while True:
            # A rebuild that finished while this request waited serves it too.
            if not force and (served := self._fresh()) is not None:
                return served
            if self._building is None:
                break
            await asyncio.wait({self._building})
        task = self._building = asyncio.create_task(self._rebuild())
        # Nobody may be left to read the outcome of a collect whose requester went away.
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        await asyncio.wait({task})
        return task.result()

    async def home_online(self) -> Served:
        """A snapshot with the online checks, always rebuilt and never cached: the cache keeps
        the offline facts the TTL is about."""
        snapshot = await asyncio.to_thread(self._collect_online, self._repo)
        return Served(snapshot, False, 0.0, self._keep(snapshot))

    def problems_page(self, snapshot_id: int, offset: int) -> tuple[str, int, bool]:
        """The `problems_text` of a kept snapshot from `offset` on, at most `PAGE_BYTES` on the
        wire, with the offset of the next page and whether this page is the last. A snapshot
        that is no longer kept is `LookupError`; an offset beyond the text is `ValueError`."""
        snapshot = self._kept.get(snapshot_id)
        if snapshot is None:
            raise LookupError(snapshot_id)
        text = problems_text(snapshot.problems)
        if offset > len(text):
            raise ValueError(offset)
        page = _clip(text[offset : offset + PAGE_BYTES], PAGE_BYTES)
        next_offset = offset + len(page)
        return page, next_offset, next_offset == len(text)


_ERRORS = {
    "bad_json": "Request is not valid JSON.",
    "bad_request": "Request has a missing or invalid field.",
    "unknown_type": "Unknown request type.",
    "too_large": "Request is too large.",
    "busy": "Too many unfinished requests.",
    "collect_failed": "Snapshot collection failed.",
    "snapshot_expired": "The snapshot is no longer kept; request it again.",
}


@dataclass(frozen=True)
class _Request:
    id: str | int | None
    type: str
    force: bool
    online: bool
    snapshot_id: int = 0
    offset: int = 0


class Rejected(Exception):
    """A request that cannot be served, with whatever of its id and type could be trusted."""

    def __init__(
        self, code: str, id: str | int | None = None, type: str | None = None
    ) -> None:
        super().__init__(code)
        self.code, self.id, self.type = code, id, type


def parse_envelope(raw: str) -> tuple[dict[str, object], str | int | None, str]:
    """The request object with its id and type; `Rejected` carries what of them could be trusted."""
    if len(raw.encode("utf-8", errors="replace")) > MAX_REQUEST_BYTES:
        raise Rejected("too_large")
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):
        raise Rejected("bad_json") from None
    if not isinstance(body, dict):
        raise Rejected("bad_request")
    request_id = body.get("id")
    if "id" in body and not (
        (isinstance(request_id, str) and len(request_id) <= MAX_ID_CHARS)
        or (isinstance(request_id, int) and not isinstance(request_id, bool))
    ):
        raise Rejected("bad_request")
    kind = body.get("type")
    if not isinstance(kind, str):
        raise Rejected("bad_request", request_id)
    return body, request_id, kind


def _parse(raw: str) -> _Request:
    body, request_id, kind = parse_envelope(raw)
    if kind == HOME_PROBLEMS_REQUEST:
        snapshot_id, offset = body.get("snapshot_id"), body.get("offset")
        if not (
            isinstance(snapshot_id, int)
            and isinstance(offset, int)
            and not isinstance(snapshot_id, bool)
            and not isinstance(offset, bool)
            and offset >= 0
        ):
            raise Rejected("bad_request", request_id, kind)
        return _Request(request_id, kind, False, False, snapshot_id, offset)
    if kind != HOME_REQUEST:
        raise Rejected("unknown_type", request_id, kind[:MAX_ID_CHARS])
    force = body.get("force", False)
    online = body.get("online", False)
    if not isinstance(force, bool) or not isinstance(online, bool):
        raise Rejected("bad_request", request_id, kind)
    return _Request(request_id, kind, force, online)


def encode(reply: dict[str, object]) -> str:
    """The reply as text that encodes as UTF-8 whatever it echoes."""
    text = json.dumps(reply, separators=(",", ":"), ensure_ascii=False)
    return _LONE_SURROGATE.sub(lambda found: f"\\u{ord(found.group()):04x}", text)


def error_reply(
    code: str,
    id: str | int | None,
    type: str | None,
    message: str | None = None,
    job_id: str | None = None,
) -> str:
    error: dict[str, object] = {"code": code, "message": message or _ERRORS[code]}
    if job_id is not None:
        error["job_id"] = job_id
    return encode(
        {
            "v": PROTOCOL_VERSION,
            "id": id,
            "type": type,
            "ok": False,
            "error": error,
        }
    )


def busy(raw: str) -> str:
    """The reply to a request that arrived while too many were unfinished; echoes what it can."""
    try:
        request = _parse(raw)
    except Rejected as rejected:
        return error_reply("busy", rejected.id, rejected.type)
    return error_reply("busy", request.id, request.type)


async def respond(raw: str, snapshots: SnapshotService) -> str:
    """The reply to one request frame. Never raises: every failure is an error reply."""
    try:
        request = _parse(raw)
    except Rejected as rejected:
        return error_reply(rejected.code, rejected.id, rejected.type)
    if request.type == HOME_PROBLEMS_REQUEST:
        return _problems_reply(request, snapshots)
    try:
        served = await (
            snapshots.home_online()
            if request.online
            else snapshots.home(force=request.force)
        )
    except Exception as exc:
        return error_reply(
            "collect_failed", request.id, request.type, type(exc).__name__
        )
    reply: dict[str, object] = {
        "v": PROTOCOL_VERSION,
        "id": request.id,
        "type": request.type,
        "ok": True,
        "cached": served.cached,
        "age_seconds": round(served.age_seconds, 3),
        "snapshot": served.snapshot.to_payload(),
    }
    # Only a reply that does not list every problem whole names where the rest is paged.
    if served.snapshot.listed_problems() != served.snapshot.problems:
        reply["problems_snapshot_id"] = served.snapshot_id
    return encode(reply)


def _problems_reply(request: _Request, snapshots: SnapshotService) -> str:
    try:
        text, next_offset, done = snapshots.problems_page(
            request.snapshot_id, request.offset
        )
    except LookupError:
        return error_reply("snapshot_expired", request.id, request.type)
    except ValueError:
        return error_reply("bad_request", request.id, request.type)
    return encode(
        {
            "v": PROTOCOL_VERSION,
            "id": request.id,
            "type": request.type,
            "ok": True,
            "text": text,
            "next": next_offset,
            "done": done,
        }
    )
