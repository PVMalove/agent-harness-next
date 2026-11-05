"""The `home.snapshot` and `home.problems` requests: parsing, the busy reply and the replies."""

from __future__ import annotations

from dataclasses import dataclass

from ....kernel.protocol import (
    HOME_PROBLEMS_REQUEST,
    HOME_REQUEST,
    MAX_ID_CHARS,
    PROTOCOL_VERSION,
)
from ...application.snapshots import SnapshotService
from . import Rejected, encode, error_reply, parse_envelope

_ERRORS = {
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
        return error_reply(
            "snapshot_expired", request.id, request.type, _ERRORS["snapshot_expired"]
        )
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
