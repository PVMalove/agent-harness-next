"""An in-process WebSocket client of an ASGI application: it speaks the ASGI websocket interface
to `create_app(runtime)` directly, so a test passes the real /ws route and the security
middleware without a socket, Uvicorn or a subprocess."""

from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from types import TracebackType
from typing import Any

from starlette.types import ASGIApp

Message = MutableMapping[str, Any]  # type: ignore[explicit-any]


class Rejected(Exception):
    """The handshake was refused with this HTTP status."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


class AsgiWebSocket:
    """One /ws connection: `async with` performs the handshake, `send_text` and `receive_text`
    exchange frames, leaving the block disconnects and waits for the application."""

    def __init__(
        self,
        app: ASGIApp,
        port: int,
        token: str,
        *,
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        self._app = app
        self._incoming: asyncio.Queue[Message] = asyncio.Queue()
        self._outgoing: asyncio.Queue[Message] = asyncio.Queue()
        self._headers = (
            headers
            if headers is not None
            else [
                (b"host", f"127.0.0.1:{port}".encode()),
                (b"authorization", f"Bearer {token}".encode()),
            ]
        )
        self._port = port
        self._task: asyncio.Task[None] | None = None

    async def _receive(self) -> Message:
        return await self._incoming.get()

    async def _send(self, message: Message) -> None:
        await self._outgoing.put(message)

    async def __aenter__(self) -> AsgiWebSocket:
        scope: Message = {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "scheme": "ws",
            "http_version": "1.1",
            "path": "/ws",
            "raw_path": b"/ws",
            "query_string": b"",
            "root_path": "",
            "headers": self._headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", self._port),
            "subprotocols": [],
            "extensions": {"websocket.http.response": {}},
            "state": {},
        }
        await self._incoming.put({"type": "websocket.connect"})

        async def serve() -> None:
            await self._app(scope, self._receive, self._send)

        self._task = asyncio.create_task(serve())
        first = await asyncio.wait_for(self._outgoing.get(), 5)
        if first["type"] == "websocket.http.response.start":
            await self._finish()
            raise Rejected(int(first["status"]))
        assert first["type"] == "websocket.accept", first
        return self

    async def send_text(self, text: str) -> None:
        await self._incoming.put({"type": "websocket.receive", "text": text})

    async def receive_text(self) -> str:
        message = await asyncio.wait_for(self._outgoing.get(), 5)
        assert message["type"] == "websocket.send", message
        return str(message["text"])

    async def _finish(self) -> None:
        if self._task is not None:
            await asyncio.wait_for(self._task, 5)

    async def __aexit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        await self._incoming.put({"type": "websocket.disconnect", "code": 1000})
        await self._finish()
