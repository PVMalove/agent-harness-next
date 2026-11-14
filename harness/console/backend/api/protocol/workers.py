"""The ``worker.steps`` and ``worker.subscribe`` requests: worker steps of one dispatch.

Request: ``{id, type, dispatch_id, offset}``; ``offset`` is the byte offset of the worker log the
client keeps, optional (0) for ``worker.subscribe``. ``worker.steps`` answers one ``page``;
``worker.subscribe`` answers a ``page`` first and then on new steps, a reset or a changed state,
until the connection ends. An unknown dispatch is ``not_found``.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from ....kernel.protocol import (
    MAX_ID_CHARS,
    PROTOCOL_VERSION,
    WORKER_STEPS_REQUEST,
    WORKER_SUBSCRIBE_REQUEST,
)
from ...application.worker_steps import WorkerNotFound, WorkerStepsQuery
from ...domain.worker_steps import StepsPage, valid_dispatch_id
from . import Rejected, encode, error_reply, parse_envelope

WORKER_TYPES = frozenset({WORKER_STEPS_REQUEST, WORKER_SUBSCRIBE_REQUEST})
_FIELDS = frozenset({"id", "type", "dispatch_id", "offset"})
NOT_FOUND = "The ledger has no such dispatch."


def worker_request_type(raw: str) -> str | None:
    """The worker request type of a frame, malformed or not; otherwise None."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return None
    return kind if kind in WORKER_TYPES else None


def _request(body: dict[str, object], kind: str) -> tuple[str, int] | None:
    dispatch_id = body.get("dispatch_id")
    offset = body.get("offset", None if kind == WORKER_STEPS_REQUEST else 0)
    if (
        set(body) - _FIELDS
        or not isinstance(dispatch_id, str)
        or not valid_dispatch_id(dispatch_id)
        or not isinstance(offset, int)
        or isinstance(offset, bool)
        or offset < 0
    ):
        return None
    return dispatch_id, offset


async def replies(raw: str, query: WorkerStepsQuery) -> AsyncGenerator[str, None]:
    """One page for ``worker.steps``, a stream of pages for ``worker.subscribe``. Never raises:
    every failure is an error reply that ends the answer."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        yield error_reply(rejected.code, rejected.id, rejected.type)
        return
    if kind not in WORKER_TYPES:
        yield error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
        return
    parsed = _request(body, kind)
    if parsed is None:
        yield error_reply("bad_request", request_id, kind)
        return
    dispatch_id, offset = parsed

    def reply(page: StepsPage) -> str:
        return encode(
            {
                "v": PROTOCOL_VERSION,
                "id": request_id,
                "type": kind,
                "ok": True,
                "page": page.to_wire(),
            }
        )

    try:
        if kind == WORKER_STEPS_REQUEST:
            yield reply(await query.read(dispatch_id, offset))
            return
        async with contextlib.aclosing(query.follow(dispatch_id, offset)) as pages:
            async for page in pages:
                yield reply(page)
    except WorkerNotFound:
        yield error_reply("not_found", request_id, kind, NOT_FOUND)
    except Exception as exc:
        yield error_reply("collect_failed", request_id, kind, type(exc).__name__)
