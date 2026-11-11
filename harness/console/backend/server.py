# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Project-bound console server; FastAPI and Uvicorn load only at startup (harness.console.backend.api)."""

from __future__ import annotations

import asyncio
import secrets
import socket

from .application.decisions import DecisionService
from .application.jobs import JobService
from .application.events import OrchestrationEvents
from .api.request_router import (
    MAX_SUBSCRIPTIONS as MAX_SUBSCRIPTIONS,
    MAX_UNFINISHED_REQUESTS as MAX_UNFINISHED_REQUESTS,
    RequestRouter,
)
from .application.screens import ScreenService
from .application.snapshots import SnapshotService
from . import composition
from pathlib import Path
from collections.abc import Callable
from typing import Protocol

_STARTUP_POLL = 0.01
DEFAULT_STATIC_ROOT = Path(__file__).resolve().parents[1] / "frontend" / "dist"


class _Discovery(Protocol):
    """The owner of the project's discovery lock and record (backend.infrastructure.discovery)."""

    def acquire(self) -> None: ...

    def publish(self, port: int, token: str) -> None: ...

    def close(self) -> None: ...


class _Serving(Protocol):
    """The embedded HTTP server as the lifecycle sees it (harness.console.backend.api.host)."""

    started: bool
    should_exit: bool

    async def serve(self, sockets: list[socket.socket] | None = None) -> None: ...


class ConsoleServer:
    """One loopback listener for one project; callers own its asynchronous lifetime."""

    def __init__(
        self,
        repo: Path,
        *,
        idle_grace_seconds: float = 30,
        snapshots: SnapshotService | None = None,
        jobs: JobService | None = None,
        decisions: DecisionService | None = None,
        events: OrchestrationEvents | None = None,
        screens: ScreenService | None = None,
        static_root: Path = DEFAULT_STATIC_ROOT,
    ) -> None:
        self.repo = repo.resolve()
        self._static_root = static_root
        parts = composition.compose(
            self.repo,
            snapshots=snapshots,
            jobs=jobs,
            decisions=decisions,
            events=events,
            screens=screens,
        )
        self._snapshots = parts.snapshots
        self._jobs = parts.jobs
        self._decisions = parts.decisions
        self._events = parts.events
        self._router = parts.router
        self._new_discovery: Callable[[Path], _Discovery] = parts.discovery
        self._idle_grace = idle_grace_seconds
        self._clients = 0
        self._idle_task: asyncio.Task[None] | None = None
        self._socket: socket.socket | None = None
        self._uvicorn: _Serving | None = None
        self._serve_task: asyncio.Task[None] | None = None
        self._discovery: _Discovery | None = None
        self._token = ""
        self._port = 0
        self._started = False
        self._closing = False
        self._closed = asyncio.Event()
        self._close_task: asyncio.Task[None] | None = None

    @property
    def port(self) -> int:
        """The OS-assigned IPv4 port, available after start()."""
        if not self._port:
            raise RuntimeError("console server has not started")
        return self._port

    @property
    def token(self) -> str:
        return self._token

    @property
    def closing(self) -> bool:
        return self._closing

    @property
    def router(self) -> RequestRouter:
        return self._router

    @property
    def static_root(self) -> Path:
        """The React build directory; served at "/" when it holds index.html."""
        return self._static_root

    def client_opened(self) -> None:
        self._clients += 1

    def client_closed(self) -> None:
        self._clients -= 1

    async def start(self) -> None:
        if self._started or self._closing:
            raise RuntimeError("console server cannot be restarted")
        from .api.app import create_app
        from .api.host import create_server

        self._started = True
        try:
            self._discovery = self._new_discovery(self.repo)
            self._discovery.acquire()
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket = listener
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            listener.setblocking(False)
            self._port = listener.getsockname()[1]
            self._token = secrets.token_hex(32)
            self._discovery.publish(self._port, self._token)
            server = create_server(create_app(self), self)
            self._uvicorn = server
            self._serve_task = asyncio.create_task(server.serve(sockets=[listener]))
            while not server.started:
                if self._serve_task.done():
                    self._serve_task.result()
                    raise RuntimeError("console server stopped during startup")
                await asyncio.sleep(_STARTUP_POLL)
            self._idle_task = asyncio.create_task(self._exit_when_idle())
        except BaseException:
            await self.close()
            raise

    async def _exit_when_idle(self) -> None:
        """Close once no client and no job has been present for the grace period."""
        loop = asyncio.get_running_loop()
        poll = min(1.0, self._idle_grace / 4)
        idle_since = loop.time()
        while True:
            await asyncio.sleep(poll)
            if self._clients or self._jobs.active_count:
                idle_since = loop.time()
            elif loop.time() - idle_since >= self._idle_grace:
                asyncio.create_task(self.close())
                return

    async def close(self) -> None:
        """Idempotently close the listener and all of this instance's connections."""
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown())
        await asyncio.shield(self._close_task)

    async def _shutdown(self) -> None:
        try:
            if self._idle_task is not None:
                self._idle_task.cancel()
            if self._uvicorn is not None:
                self._uvicorn.should_exit = True
            if self._serve_task is not None:
                await asyncio.gather(self._serve_task, return_exceptions=True)
            if self._socket is not None:
                self._socket.close()
            await self._jobs.close()
            await self._events.close()
        finally:
            try:
                if self._discovery is not None:
                    self._discovery.close()
            finally:
                self._closed.set()

    async def wait_closed(self) -> None:
        await self._closed.wait()


async def _serve(repo: Path) -> None:
    server = ConsoleServer(repo)
    try:
        await server.start()
        await server.wait_closed()
    finally:
        await server.close()


def run(repo: Path) -> None:
    """Serve the project until the idle rule stops the server; Ctrl-C ends it quietly."""
    try:
        asyncio.run(_serve(repo))
    except KeyboardInterrupt:
        pass
