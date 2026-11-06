"""The screen snapshot requests of Reports, Orchestration, Recovery, Container route, Diagnostics,
Harness, Repo Map, «Открыть проект», «Справка», «Обновить Harness» and «Настройка» and the
`snapshot.page` request that completes them: parsing and the replies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from ....kernel.protocol import (
    CONFIGURATION_REQUEST,
    DIAGNOSTICS_REQUEST,
    HARNESS_OVERVIEW_REQUEST,
    HARNESS_REQUEST,
    HELP_REQUEST,
    LOCK_REQUEST,
    MAINTENANCE_REQUEST,
    MAX_ID_CHARS,
    MAX_PATH_CHARS,
    MAX_SKIPPED,
    OPEN_PROJECT_REQUEST,
    ORCHESTRATION_REQUEST,
    PAGE_REQUEST,
    PROTOCOL_VERSION,
    RECOVERY_REQUEST,
    REPO_MAP_REQUEST,
    REPORT_REQUEST,
    REPORTS_REQUEST,
    ROUTE_REQUEST,
    TASK_BOARD_REQUEST,
    TASK_BOARD_SPECS_REQUEST,
    TIMELINE_REQUEST,
    UPDATE_DIFF_REQUEST,
    UPDATE_HARNESS_REQUEST,
)
from ....kernel.help_text import HELP_LANGUAGES
from ...application.ports import SpecNotFound
from ...application.screens import NotFound, Paged, ScreenService
from . import Rejected, encode, error_reply, parse_envelope

_ERRORS = {
    "not_found": "The ledger has no such report or batch.",
    "snapshot_expired": "The snapshot is no longer kept; request it again.",
    "spec_not_found": "The tracker has no such open spec.",
}

# Every request type with the fields it may carry beside `id` and `type`.
_FIELDS: dict[str, frozenset[str]] = {
    REPORTS_REQUEST: frozenset({"force", "online"}),
    REPORT_REQUEST: frozenset({"dispatch_id"}),
    TIMELINE_REQUEST: frozenset({"batch_id"}),
    ORCHESTRATION_REQUEST: frozenset({"force"}),
    LOCK_REQUEST: frozenset(),
    RECOVERY_REQUEST: frozenset({"batch", "skip", "force"}),
    ROUTE_REQUEST: frozenset({"batch", "role", "runtime"}),
    PAGE_REQUEST: frozenset({"snapshot_id", "offset"}),
    TASK_BOARD_SPECS_REQUEST: frozenset({"force"}),
    TASK_BOARD_REQUEST: frozenset({"spec", "force"}),
    DIAGNOSTICS_REQUEST: frozenset({"online", "force"}),
    HARNESS_REQUEST: frozenset({"force"}),
    # A typed reply, not paged: the state, the drift and the pipeline usage counts.
    HARNESS_OVERVIEW_REQUEST: frozenset({"force"}),
    MAINTENANCE_REQUEST: frozenset({"force"}),
    REPO_MAP_REQUEST: frozenset({"force"}),
    # No project field: the server serves one project and never switches it.
    OPEN_PROJECT_REQUEST: frozenset({"force"}),
    HELP_REQUEST: frozenset({"language"}),
    UPDATE_HARNESS_REQUEST: frozenset({"force"}),
    # The path is checked against the drift report before anything is read.
    UPDATE_DIFF_REQUEST: frozenset({"path", "force"}),
    # Read only: a pending transaction is reported, never recovered.
    CONFIGURATION_REQUEST: frozenset({"force"}),
}
# The replies that carry whether they came from the cache and how old it is.
_CACHED_TYPES = frozenset(
    {TASK_BOARD_SPECS_REQUEST, MAINTENANCE_REQUEST}
    | {kind for kind in _FIELDS if kind.endswith(".snapshot")}
)
SCREEN_TYPES = frozenset(_FIELDS)


def is_screen_request(raw: str) -> bool:
    """True for a request of a screen snapshot type or `snapshot.page`, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind in SCREEN_TYPES


class _Bad(Exception):
    pass


def _flag(body: dict[str, object], name: str) -> bool:
    value = body.get(name, False)
    if not isinstance(value, bool):
        raise _Bad(name)
    return value


def _id(body: dict[str, object], name: str, default: str | None = None) -> str:
    """A bounded id; without `default` it is required and may not be empty."""
    value = body.get(name, default)
    if not isinstance(value, str) or len(value) > MAX_ID_CHARS:
        raise _Bad(name)
    if default is None and not value:
        raise _Bad(name)
    return value


def _path(body: dict[str, object]) -> str:
    """A required, bounded project-relative path."""
    value = body.get("path")
    if not isinstance(value, str) or not 0 < len(value) <= MAX_PATH_CHARS:
        raise _Bad("path")
    return value


def _count(body: dict[str, object], name: str) -> int:
    value = body.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _Bad(name)
    return value


def _skip(body: dict[str, object]) -> tuple[str, ...]:
    value = body.get("skip", [])
    if not isinstance(value, list) or len(value) > MAX_SKIPPED:
        raise _Bad("skip")
    if not all(
        isinstance(item, str) and 0 < len(item) <= MAX_ID_CHARS for item in value
    ):
        raise _Bad("skip")
    return tuple(value)


def _call(
    kind: str, body: dict[str, object], screens: ScreenService
) -> Callable[[], Awaitable[Paged | dict[str, object]]]:
    """The service call a valid request asks for; `_Bad` for a missing or invalid field."""
    if kind == REPORTS_REQUEST:
        force, online = _flag(body, "force"), _flag(body, "online")
        return lambda: screens.reports(force=force, online=online)
    if kind == REPORT_REQUEST:
        dispatch_id = _id(body, "dispatch_id")
        return lambda: screens.report(dispatch_id)
    if kind == TIMELINE_REQUEST:
        batch_id = _id(body, "batch_id")
        return lambda: screens.timeline(batch_id)
    if kind == ORCHESTRATION_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.orchestration(force=force)
    if kind == LOCK_REQUEST:
        return screens.lock
    if kind == RECOVERY_REQUEST:
        batch, skip, force = _id(body, "batch", ""), _skip(body), _flag(body, "force")
        return lambda: screens.recovery(batch, skip, force=force)
    if kind == TASK_BOARD_SPECS_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.task_board_specs(force=force)
    if kind == TASK_BOARD_REQUEST:
        spec, force = _id(body, "spec"), _flag(body, "force")
        return lambda: screens.task_board(spec, force=force)
    if kind == DIAGNOSTICS_REQUEST:
        online, force = _flag(body, "online"), _flag(body, "force")
        return lambda: screens.diagnostics(online=online, force=force)
    if kind == HARNESS_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.harness(force=force)
    if kind == HARNESS_OVERVIEW_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.harness_overview(force=force)
    if kind == MAINTENANCE_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.maintenance(force=force)
    if kind == REPO_MAP_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.repo_map(force=force)
    if kind == OPEN_PROJECT_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.open_project(force=force)
    if kind == HELP_REQUEST:
        language = body.get("language")
        if language not in HELP_LANGUAGES:
            raise _Bad("language")
        return lambda: screens.help(str(language))
    if kind == UPDATE_HARNESS_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.update_harness(force=force)
    if kind == UPDATE_DIFF_REQUEST:
        path, force = _path(body), _flag(body, "force")
        return lambda: screens.update_diff(path, force=force)
    if kind == CONFIGURATION_REQUEST:
        force = _flag(body, "force")
        return lambda: screens.configuration(force=force)
    batch, role = _id(body, "batch", ""), _id(body, "role", "developer")
    runtime = _id(body, "runtime", "")
    if not role:
        raise _Bad("role")
    return lambda: screens.container_route(batch, role, runtime)


def _ok(request_id: str | int | None, kind: str, **fields: object) -> str:
    return encode(
        {"v": PROTOCOL_VERSION, "id": request_id, "type": kind, "ok": True, **fields}
    )


def _page_reply(
    request_id: str | int | None, kind: str, body: dict[str, object], screens: ScreenService
) -> str:
    try:
        snapshot_id, offset = _count(body, "snapshot_id"), _count(body, "offset")
    except _Bad:
        return error_reply("bad_request", request_id, kind)
    try:
        text, next_offset, done = screens.page(snapshot_id, offset)
    except LookupError:
        return error_reply(
            "snapshot_expired", request_id, kind, _ERRORS["snapshot_expired"]
        )
    except ValueError:
        return error_reply("bad_request", request_id, kind)
    return _ok(request_id, kind, text=text, next=next_offset, done=done)


async def respond(raw: str, screens: ScreenService) -> str:
    """The reply to one screen request frame. Never raises: every failure is an error reply."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        return error_reply(rejected.code, rejected.id, rejected.type)
    if kind not in SCREEN_TYPES:
        return error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
    if set(body) - {"id", "type"} - _FIELDS[kind]:
        return error_reply("bad_request", request_id, kind)
    if kind == PAGE_REQUEST:
        return _page_reply(request_id, kind, body, screens)
    try:
        call = _call(kind, body, screens)
    except _Bad:
        return error_reply("bad_request", request_id, kind)
    try:
        served = await call()
    except SpecNotFound:
        return error_reply("not_found", request_id, kind, _ERRORS["spec_not_found"])
    except NotFound:
        return error_reply("not_found", request_id, kind, _ERRORS["not_found"])
    except Exception as exc:
        return error_reply("collect_failed", request_id, kind, type(exc).__name__)
    if isinstance(served, dict):
        return _ok(request_id, kind, **served)
    fields: dict[str, object] = {
        "snapshot_id": served.snapshot_id,
        "text": served.text,
        "next": served.next,
        "done": served.done,
    }
    if kind in _CACHED_TYPES:
        fields.update(cached=served.cached, age_seconds=served.age_seconds)
    return _ok(request_id, kind, **fields)
