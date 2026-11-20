"""The ``decisions.snapshot`` request: the pending human decisions of the project."""

from __future__ import annotations

from ....kernel.protocol import MAX_ID_CHARS, PROTOCOL_VERSION
from ...application.decisions import DecisionService
from . import Rejected, encode, error_reply, parse_envelope

DECISIONS_REQUEST = "decisions.snapshot"


def is_decisions_request(raw: str) -> bool:
    """True for a request of type ``decisions.snapshot``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == DECISIONS_REQUEST


async def respond(raw: str, service: DecisionService) -> str:
    """The reply to one ``decisions.snapshot`` frame. Never raises: every failure is an error reply."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        return error_reply(rejected.code, rejected.id, rejected.type)
    if kind != DECISIONS_REQUEST:
        return error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
    if set(body) - {"id", "type"}:
        return error_reply("bad_request", request_id, kind)
    try:
        snapshot = await service.snapshot()
    except Exception as exc:
        return error_reply("collect_failed", request_id, kind, type(exc).__name__)
    return encode(
        {
            "v": PROTOCOL_VERSION,
            "id": request_id,
            "type": kind,
            "ok": True,
            "snapshot": snapshot.to_payload(),
        }
    )
