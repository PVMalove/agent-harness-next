"""The console protocol envelope: reading a request's id and type, encoding a reply and the
error replies with the messages every request type shares."""

from __future__ import annotations

import json

from ....kernel.protocol import (
    MAX_ID_CHARS,
    MAX_REQUEST_BYTES,
    PROTOCOL_VERSION,
    _LONE_SURROGATE,
)

_ERRORS = {
    "bad_json": "Request is not valid JSON.",
    "bad_request": "Request has a missing or invalid field.",
    "unknown_type": "Unknown request type.",
    "too_large": "Request is too large.",
    "busy": "Too many unfinished requests.",
    "collect_failed": "Snapshot collection failed.",
}


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
