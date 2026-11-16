"""The ``advisor.check``, ``advisor.ask`` and ``advisor.cancel`` requests: AI advice about one
«Настройка» parameter. A frame names the parameter only; the server reads the saved files, so no
draft, value, command, path or token travels with the request."""

from __future__ import annotations

import re
import threading

from ....kernel.protocol import (
    ADVISOR_ASK_REQUEST,
    ADVISOR_CANCEL_REQUEST,
    ADVISOR_CHECK_REQUEST,
    MAX_ID_CHARS,
    PROTOCOL_VERSION,
)
from ...application.advisor import AdvisorBusy, AdvisorService
from ...application.ports import AdviceNotFound
from . import Rejected, encode, error_reply, parse_envelope

_FIELDS: dict[str, frozenset[str]] = {
    ADVISOR_CHECK_REQUEST: frozenset({"id", "type", "provider"}),
    ADVISOR_ASK_REQUEST: frozenset({"id", "type", "provider", "file", "path"}),
    ADVISOR_CANCEL_REQUEST: frozenset({"id", "type", "request_id"}),
}
PROVIDERS = frozenset({"codex", "claude"})
FILES = frozenset({"project.json", "orchestration.json"})
MAX_PATH_PARTS = 8
PATH_PART = re.compile(r"[A-Za-z0-9_.-]{1,64}")
NOT_FOUND = "The configuration has no such wizard parameter."

# The pending asks of one connection: request id -> the Event that stops its CLI.
Pending = dict[str | int, threading.Event]


def advisor_request_type(raw: str) -> str | None:
    """The advisor request type of a frame, malformed or not; None for other frames."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return None
    return kind if kind in _FIELDS else None


def _is_id(value: object) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= MAX_ID_CHARS) or (
        isinstance(value, int) and not isinstance(value, bool)
    )


def _path(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list) or not 0 < len(value) <= MAX_PATH_PARTS:
        return None
    if not all(isinstance(part, str) and PATH_PART.fullmatch(part) for part in value):
        return None
    return tuple(value)


def _ok(request_id: str | int | None, kind: str, **fields: object) -> str:
    return encode(
        {"v": PROTOCOL_VERSION, "id": request_id, "type": kind, "ok": True, **fields}
    )


async def respond(raw: str, service: AdvisorService | None, pending: Pending) -> str:
    """The one reply to an advisor frame. Never raises, except for the cancellation of the
    answering task, which stops the CLI first."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        return error_reply(rejected.code, rejected.id, rejected.type)
    if kind not in _FIELDS or service is None:
        return error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
    if set(body) - _FIELDS[kind]:
        return error_reply("bad_request", request_id, kind)
    if kind == ADVISOR_CANCEL_REQUEST:
        target = body.get("request_id")
        if not _is_id(target):
            return error_reply("bad_request", request_id, kind)
        assert isinstance(target, (str, int))
        event = pending.get(target)
        cancelled = event is not None and not event.is_set()
        if event is not None:
            event.set()
        return _ok(request_id, kind, cancelled=cancelled)
    provider = body.get("provider")
    if provider not in PROVIDERS:
        return error_reply("bad_request", request_id, kind)
    assert isinstance(provider, str)
    if kind == ADVISOR_CHECK_REQUEST:
        try:
            status = await service.check(provider)
        except Exception as exc:
            return error_reply("collect_failed", request_id, kind, type(exc).__name__)
        return _ok(request_id, kind, status=dict(status))
    file, path = body.get("file"), _path(body.get("path"))
    if not _is_id(request_id) or file not in FILES or path is None:
        return error_reply("bad_request", request_id, kind)
    assert isinstance(file, str) and request_id is not None
    if pending:
        return error_reply("busy", request_id, kind)
    cancel = threading.Event()
    pending[request_id] = cancel
    try:
        answer = await service.ask(provider, file, path, cancel)
    except AdvisorBusy:
        return error_reply("busy", request_id, kind)
    except AdviceNotFound:
        return error_reply("not_found", request_id, kind, NOT_FOUND)
    except Exception as exc:
        return error_reply("collect_failed", request_id, kind, type(exc).__name__)
    finally:
        cancel.set()
        pending.pop(request_id, None)
    return _ok(request_id, kind, **answer)
