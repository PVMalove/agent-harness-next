"""The ``job.*`` requests of the console protocol.

Requests use ``job.start(command_id, values?, confirmed?, confirmation?, plan_digest?, client?)``,
``job.cancel(job_id, confirmed?)``, ``job.get/job.subscribe(job_id, cursor=0)``, ``job.list`` and
``job.catalog(section)``. Replies carry a ``job`` snapshot, the ``jobs`` summaries for
``job.list`` (``mutating`` marks the holder of the mutation slot), or the ``commands`` of a
section for ``job.catalog``: the server's own catalog entries with their reversibility class,
confirmation, inputs and availability in the served project. An unknown section is
``bad_request``. The cursor counts
output fragments, starting at zero. Each snapshot contains the next bounded batch and its new
cursor; ``done`` means execution and replay ended. Subscriptions own no execution task. A job keeps
a bounded output, and ``truncated`` marks the cut.

The optional ``client`` identifies the initiating surface as ``tui`` or ``browser``; older
clients without it are recorded as ``unknown``.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator

from ....kernel.protocol import MAX_ID_CHARS, PROTOCOL_VERSION
from ...application.jobs import JobService
from ...domain.jobs import JobRejected
from . import Rejected, encode, error_reply, parse_envelope

_FIELDS = {
    "job.start": {
        "id",
        "type",
        "command_id",
        "values",
        "confirmed",
        "confirmation",
        "plan_digest",
        "client",
    },
    "job.get": {"id", "type", "job_id", "cursor"},
    "job.subscribe": {"id", "type", "job_id", "cursor"},
    "job.cancel": {"id", "type", "job_id", "confirmed"},
    "job.list": {"id", "type"},
    "job.catalog": {"id", "type", "section"},
}

_ERRORS = {
    "unknown_command": "Unknown catalog command.",
    "confirmation_required": "The command needs an explicit confirmation.",
    "plan_required": "Preview the cleanup plan and send its plan_digest.",
    "unavailable_command": "The command is unavailable in this project.",
    "start_failed": "The command could not be prepared.",
    "busy": "Too many running jobs.",
    "not_running": "The job is not running.",
    "unknown_job": "Unknown job.",
    "invalid_cursor": "Cursor is outside the job output.",
}


def job_request_type(raw: str) -> str | None:
    """The type of a `job.*` request; malformed and other requests stay with the snapshot protocol."""
    try:
        _, _, kind = parse_envelope(raw)
    except Rejected:
        return None
    return kind if kind.startswith("job.") else None


async def replies(raw: str, jobs: JobService) -> AsyncGenerator[str, None]:
    """Reply once to start/get/list, or stream successive non-overlapping subscription
    batches. Never raises: every failure is an error reply."""
    try:
        body, request_id, kind = parse_envelope(raw)
    except Rejected as rejected:
        yield error_reply(rejected.code, rejected.id, rejected.type)
        return
    echoed = kind[:MAX_ID_CHARS]
    envelope = {"v": PROTOCOL_VERSION, "id": request_id, "type": echoed}
    try:
        if kind not in _FIELDS:
            raise JobRejected("unknown_type")
        if set(body) - _FIELDS[kind]:
            raise JobRejected("bad_request")
        if kind == "job.list":
            yield encode({**envelope, "ok": True, "jobs": jobs.jobs()})
            return
        if kind == "job.catalog":
            commands = jobs.commands(body.get("section"))
            yield encode({**envelope, "ok": True, "commands": commands})
            return
        if kind == "job.start":
            job = jobs.start(body)
        elif kind == "job.cancel":
            job = await jobs.cancel(body)
        else:
            job = jobs.job(body)
        cursor = body.get("cursor", 0)
        follow = jobs.follow(job, cursor, subscribe=kind == "job.subscribe")
        async with contextlib.aclosing(follow) as snapshots:
            async for snapshot in snapshots:
                yield encode({**envelope, "ok": True, "job": snapshot})
    except JobRejected as rejected:
        yield error_reply(
            rejected.code,
            request_id,
            echoed,
            rejected.message or _ERRORS.get(rejected.code),
            rejected.job_id,
        )
