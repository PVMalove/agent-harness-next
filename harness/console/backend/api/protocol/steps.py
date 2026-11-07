"""The ``steps.subscribe`` request: the live step list of the web console.

Request: ``{id, type: "steps.subscribe"}`` without other fields. Replies carry ``kind``:
``roster`` (first, then on every change of the followed dispatches or of the orchestration source;
``reset`` asks the client to drop the steps it holds) or ``steps`` (a non-empty group of agent and
orchestration steps, each tagged by ``origin``). The stream ends with the connection.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from ....kernel.protocol import MAX_ID_CHARS, PROTOCOL_VERSION
from ...application.live_steps import LiveSteps, RosterItem, StepsItem
from . import Rejected, encode, error_reply, parse_envelope

STEPS_SUBSCRIBE = "steps.subscribe"
FIELDS = frozenset({"id", "type"})


def is_steps_request(raw: str) -> bool:
    """True for a request of type ``steps.subscribe``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == STEPS_SUBSCRIBE


async def replies(raw: str, steps: LiveSteps) -> AsyncGenerator[str, None]:
    """Stream the roster and the steps until the connection ends. Never raises: every failure
    is an error reply that ends the stream."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        yield error_reply(rejected.code, rejected.id, rejected.type)
        return
    if kind != STEPS_SUBSCRIBE:
        yield error_reply("unknown_type", request_id, kind[:MAX_ID_CHARS])
        return
    if set(body) - FIELDS:
        yield error_reply("bad_request", request_id, kind)
        return
    envelope = {"v": PROTOCOL_VERSION, "id": request_id, "type": kind, "ok": True}
    try:
        async with contextlib.aclosing(steps.subscribe()) as items:
            async for item in items:
                if isinstance(item, RosterItem):
                    yield encode(
                        {
                            **envelope,
                            "kind": "roster",
                            "reset": item.reset,
                            "orchestration": item.orchestration,
                            "dispatches": [
                                entry.to_wire() for entry in item.dispatches
                            ],
                        }
                    )
                elif isinstance(item, StepsItem):
                    yield encode(
                        {
                            **envelope,
                            "kind": "steps",
                            "steps": [step.to_wire() for step in item.steps],
                        }
                    )
    except Exception as exc:
        yield error_reply("collect_failed", request_id, kind, type(exc).__name__)
