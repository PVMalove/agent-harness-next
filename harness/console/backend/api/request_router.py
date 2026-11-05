"""Routes console request frames to the services; slots, busy replies and answer tasks.

The transport hands over decoded text frames and an async ``send`` that returns False once the
peer is gone. No transport or framework module is imported here.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

from ..application.decisions import DecisionService
from .protocol.decisions import is_decisions_request
from .protocol.decisions import respond as respond_decisions
from ..application.jobs import JobService
from .protocol.jobs import job_request_type
from .protocol.jobs import replies as job_replies
from ..application.events import OrchestrationEvents
from .protocol.events import is_orchestration_request
from .protocol.events import replies as event_replies
from ..application.screens import ScreenService
from .protocol.screens import is_screen_request
from .protocol.screens import respond as respond_screens
from ..application.snapshots import SnapshotService
from .protocol.snapshots import busy, respond

MAX_UNFINISHED_REQUESTS = 4
# A subscription stays unfinished while its job runs or its stream is open, so it never takes a
# request slot.
MAX_SUBSCRIPTIONS = 4

Send = Callable[[str], Awaitable[bool]]


class RouterConnection:
    """The request slots of one WebSocket connection."""

    def __init__(
        self,
        router: RequestRouter,
        send: Send,
        on_failure: Callable[[], None] | None,
    ) -> None:
        self._router = router
        self._send = send
        self._on_failure = on_failure
        self.lock = asyncio.Lock()
        self._requests: set[asyncio.Task[None]] = set()
        self._subscriptions: set[asyncio.Task[None]] = set()

    @property
    def unfinished(self) -> int:
        return len(self._requests) + len(self._subscriptions)

    async def submit(self, raw: str) -> None:
        """Start answering one text frame, or reply busy when its slots are full."""
        job_type = job_request_type(raw)
        pending, limit = (
            (self._subscriptions, MAX_SUBSCRIPTIONS)
            if job_type == "job.subscribe" or is_orchestration_request(raw)
            else (self._requests, MAX_UNFINISHED_REQUESTS)
        )
        if len(pending) >= limit:
            await self._reply(busy(raw))
            return
        task = asyncio.create_task(self._answer(raw, job_type))
        pending.add(task)
        task.add_done_callback(pending.discard)

    async def _reply(self, reply: str) -> bool:
        async with self.lock:
            return await self._send(reply)

    async def _stream(self, replies: AsyncIterator[str]) -> None:
        async for reply in replies:
            if not await self._reply(reply):
                return

    async def _answer(self, raw: str, job_type: str | None) -> None:
        """Answer one request beside the transport, so a slow check never stalls Ping or Close."""
        router = self._router
        try:
            if job_type is not None:
                async with contextlib.aclosing(job_replies(raw, router.jobs)) as replies:
                    await self._stream(replies)
            elif is_orchestration_request(raw):
                async with contextlib.aclosing(event_replies(raw, router.events)) as replies:
                    await self._stream(replies)
            elif is_decisions_request(raw):
                await self._reply(await respond_decisions(raw, router.decisions))
            elif is_screen_request(raw):
                await self._reply(await respond_screens(raw, router.screens))
            else:
                await self._reply(await respond(raw, router.snapshots))
        except Exception:
            # A reply that cannot be produced or sent ends the connection.
            if self._on_failure is not None:
                self._on_failure()

    async def aclose(self) -> None:
        """Cancel and await every unfinished answer of this connection."""
        unfinished = self._requests | self._subscriptions
        for task in unfinished:
            task.cancel()
        await asyncio.gather(*unfinished, return_exceptions=True)


class RequestRouter:
    """Shared services of one console server; open() gives each connection its own slots."""

    def __init__(
        self,
        snapshots: SnapshotService,
        jobs: JobService,
        decisions: DecisionService,
        events: OrchestrationEvents,
        screens: ScreenService,
    ) -> None:
        self.snapshots = snapshots
        self.jobs = jobs
        self.decisions = decisions
        self.events = events
        self.screens = screens

    def open(
        self, send: Send, on_failure: Callable[[], None] | None = None
    ) -> RouterConnection:
        return RouterConnection(self, send, on_failure)
