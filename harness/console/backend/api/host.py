"""Embedded Uvicorn: ConsoleServer owns the socket, the signals and the lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Generator

import uvicorn
from fastapi import FastAPI
from uvicorn._types import ASGISendEvent
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.websockets.websockets_sansio_impl import (
    WebSocketsSansIOProtocol,
)
from websockets.http11 import Request

from ..server import CLOSE_TIMEOUT, HEADER_LIMIT, MESSAGE_LIMIT
from . import Runtime
from .security import CLOSING, REJECTED, rejection_headers, websocket_status


def _websocket_protocol(runtime: Runtime) -> type[WebSocketsSansIOProtocol]:
    class ConsoleWebSocket(WebSocketsSansIOProtocol):
        """Admission runs before the WebSocket handshake checks, in the order of the rules.

        A peer that never answers our Close frame is released after CLOSE_TIMEOUT.
        """

        def connection_made(self, transport: asyncio.BaseTransport) -> None:
            super().connection_made(transport)
            self.close_timeout = CLOSE_TIMEOUT
            # Uvicorn hands over only the request head; bytes that arrived with it (a first
            # frame) are still in the HTTP parser and are replayed once the handshake completes.
            http = transport.get_protocol()
            self._early = (
                http.conn.trailing_data[0] if isinstance(http, H11Protocol) else b""
            )

        async def send(self, message: ASGISendEvent) -> None:
            await super().send(message)
            if message["type"] == "websocket.accept" and self._early:
                early, self._early = self._early, b""
                self.data_received(early)

        def handle_connect(self, event: Request) -> None:
            path, _, query = event.path.partition("?")
            headers = [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in event.headers.raw_items()
            ]
            status = websocket_status(runtime, headers, path, query.encode("latin-1"))
            if status is None:
                super().handle_connect(event)
            else:
                self._refuse(status)

        def data_received(self, data: bytes) -> None:
            super().data_received(data)
            if not self.handshake_initiated and self.conn.handshake_exc is not None:
                # websockets refused to parse the request at all, e.g. one with a body.
                self._refuse(400)

        def _refuse(self, status: int) -> None:
            body = CLOSING if status == 503 else REJECTED
            response = self.conn.reject(status, body.decode())
            for name, value in rejection_headers(status, body):
                if name.decode() not in response.headers:
                    response.headers[name.decode()] = value.decode()
            self.handshake_initiated = True
            self.handshake_complete = True
            self.close_sent = True
            # Written directly: after a parse failure the sans-I/O protocol already ended its output.
            self.transport.write(response.serialize())
            self.transport.close()

    return ConsoleWebSocket


class _EmbeddedServer(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        # The owner handles signals; Uvicorn must not re-raise them after serve().
        yield


def create_server(app: FastAPI, runtime: Runtime) -> uvicorn.Server:
    config = uvicorn.Config(
        app,
        http="h11",
        ws=_websocket_protocol(runtime),
        lifespan="off",
        log_config=None,
        log_level="warning",
        access_log=False,
        server_header=False,
        date_header=False,
        proxy_headers=False,
        ws_max_size=MESSAGE_LIMIT,
        ws_per_message_deflate=False,
        ws_ping_interval=None,
        ws_ping_timeout=None,
        h11_max_incomplete_event_size=HEADER_LIMIT,
        timeout_graceful_shutdown=1,
    )
    return _EmbeddedServer(config)
