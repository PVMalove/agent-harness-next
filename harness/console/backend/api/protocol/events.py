"""The ``orchestration.subscribe`` request: a stream of the orchestration source state and events.

Request: ``{id, type: "orchestration.subscribe", cursor?}``. Without a cursor the stream starts at
the head. Replies carry ``kind``: ``source`` (always first, then on every change of the source
state) or ``events`` (a non-empty batch with the cursor of its last event). A cursor is
``<journal>-<seq>``.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from ....kernel.protocol import MAX_ID_CHARS, PROTOCOL_VERSION
from ...application.events import (
    EventsItem,
    OrchestrationEvents,
    SourceItem,
    SubscriptionRejected,
)
from . import Rejected, encode, error_reply, parse_envelope

ORCHESTRATION_SUBSCRIBE = "orchestration.subscribe"
_FIELDS = frozenset({"id", "type", "cursor"})


def is_orchestration_request(raw: str) -> bool:
    """True for a request of type ``orchestration.subscribe``, malformed or not."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return False
    return kind == ORCHESTRATION_SUBSCRIBE


async def replies(raw: str, events: OrchestrationEvents) -> AsyncGenerator[str, None]:
    """Stream the source state and the events after the cursor until the connection ends.
    Never raises: every failure is an error reply that ends the stream."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        yield error_reply(rejected.code, rejected.id, rejected.type)
        return
    echoed = kind[:MAX_ID_CHARS]
    envelope = {"v": PROTOCOL_VERSION, "id": request_id, "type": echoed, "ok": True}
    try:
        if kind != ORCHESTRATION_SUBSCRIBE:
            raise SubscriptionRejected("unknown_type")
        if set(body) - _FIELDS or not isinstance(body.get("cursor", ""), str):
            raise SubscriptionRejected("bad_request")
        cursor = body.get("cursor")
        subscription = events.subscribe(cursor if isinstance(cursor, str) else None)
        async with contextlib.aclosing(subscription) as items:
            async for item in items:
                if isinstance(item, SourceItem):
                    yield encode(
                        {
                            **envelope,
                            "kind": "source",
                            "cursor": item.cursor,
                            "source": item.source,
                        }
                    )
                elif isinstance(item, EventsItem):
                    yield encode(
                        {
                            **envelope,
                            "kind": "events",
                            "cursor": item.cursor,
                            "events": item.events,
                        }
                    )
    except SubscriptionRejected as rejected:
        yield error_reply(rejected.code, request_id, echoed, rejected.message)
