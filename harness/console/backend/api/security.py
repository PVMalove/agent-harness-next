"""Pure ASGI middleware: admission of every HTTP request and WebSocket handshake."""

from __future__ import annotations

import asyncio

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import admission
from ..server import CLOSE_TIMEOUT, HEADER_LIMIT
from . import Runtime

REJECTED = b"Request rejected\n"
CLOSING = b"Console is closing\n"
SECURITY_HEADERS = [
    (b"Cache-Control", b"no-store"),
    (b"X-Content-Type-Options", b"nosniff"),
    (b"X-Frame-Options", b"DENY"),
    (
        b"Content-Security-Policy",
        b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    ),
]


def rejection_headers(status: int, body: bytes) -> list[tuple[bytes, bytes]]:
    headers = [
        *SECURITY_HEADERS,
        (b"Content-Type", b"text/plain; charset=utf-8"),
        (b"Content-Length", str(len(body)).encode()),
        (b"Connection", b"close"),
    ]
    if status == 405:
        headers.append((b"Allow", admission.ALLOWED_METHODS))
    return headers


async def _drain(receive: Receive) -> None:
    """Read and drop the unread request body, so closing never resets the final response."""
    try:
        async with asyncio.timeout(CLOSE_TIMEOUT):
            while True:
                message = await receive()
                if message["type"] != "http.request" or not message.get("more_body"):
                    return
    except TimeoutError:
        pass


def _oversized(headers: admission.Headers) -> bool:
    """The request head exceeds HEADER_LIMIT even when it arrived in one read."""
    return sum(len(name) + len(value) + 4 for name, value in headers) > HEADER_LIMIT


def websocket_status(
    runtime: Runtime, headers: admission.Headers, path: str, query: bytes
) -> int | None:
    """The rejection status of a WebSocket handshake; 503 while the server closes."""
    if _oversized(headers):
        return 400
    status = admission.request_status(
        headers, b"GET", runtime.port
    ) or admission.upgrade_status(
        headers, b"GET", path, query, runtime.port, runtime.token
    )
    if status is None and runtime.closing:
        return 503
    return status


class SecurityMiddleware:
    """Rejects before routing; adds the security headers a response does not set itself."""

    def __init__(self, app: ASGIApp, runtime: Runtime) -> None:
        self.app = app
        self.runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await self._http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._websocket(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def _http(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = scope["headers"]
        method = str(scope["method"]).encode()
        status = (
            400
            if _oversized(headers)
            else admission.request_status(headers, method, self.runtime.port)
        )
        if status is None and scope["query_string"]:
            status = 404
        if status is not None:
            # The final status precedes the body: no 100 Continue, the body is drained after.
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": rejection_headers(status, REJECTED),
                }
            )
            await _drain(receive)
            await send({"type": "http.response.body", "body": REJECTED})
            return

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                own = message.get("headers", [])
                names = {name.lower() for name, _ in own}
                extra = [
                    (name, value)
                    for name, value in [*SECURITY_HEADERS, (b"Connection", b"close")]
                    if name.lower() not in names
                ]
                message = {**message, "headers": [*extra, *own]}
            await send(message)

        await self.app(scope, receive, secured)

    async def _websocket(self, scope: Scope, receive: Receive, send: Send) -> None:
        status = websocket_status(
            self.runtime, scope["headers"], str(scope["path"]), scope["query_string"]
        )
        if status is None:
            await self.app(scope, receive, send)
            return
        body = CLOSING if status == 503 else REJECTED
        await send(
            {
                "type": "websocket.http.response.start",
                "status": status,
                "headers": rejection_headers(status, body),
            }
        )
        await send({"type": "websocket.http.response.body", "body": body})
