"""Project-bound asyncio console transport; optional dependencies load only at startup."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
import secrets

from .decisions import DecisionService, is_decisions_request
from .decisions import respond as respond_decisions
from .discovery import Discovery
from .jobs import JobService, job_request_type
from .orchestration_events import OrchestrationEvents, is_orchestration_request
from .snapshots import SnapshotService, busy, respond
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

if TYPE_CHECKING:
    import h11
    from websockets.server import ServerProtocol
    from .web import WebHome

HEADER_LIMIT = 16384
HEADER_TIMEOUT = 5.0
CLOSE_TIMEOUT = 0.5
READ_CHUNK = 16384
MESSAGE_LIMIT = 65536
MAX_UNFINISHED_REQUESTS = 4
# A subscription stays unfinished while its job runs or its stream is open, so it never takes a
# request slot.
MAX_SUBSCRIPTIONS = 4
PageResponse = tuple[int, bytes | None, str, list[tuple[bytes, bytes]]]

# This independent logger never propagates protocol headers, even under root DEBUG.
_PROTOCOL_LOGGER = logging.Logger("harness.console.protocol")
_PROTOCOL_LOGGER.disabled = True
_PROTOCOL_LOGGER.propagate = False

_SECURITY_HEADERS = [
    (b"Cache-Control", b"no-store"),
    (b"Referrer-Policy", b"no-referrer"),
    (b"X-Content-Type-Options", b"nosniff"),
    (b"X-Frame-Options", b"DENY"),
    (
        b"Content-Security-Policy",
        b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
    ),
]


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
    ) -> None:
        self.repo = repo.resolve()
        self._snapshots = snapshots or SnapshotService(self.repo)
        self._jobs = jobs or JobService(self.repo)
        self._decisions = decisions or DecisionService(self.repo)
        self._events = events or OrchestrationEvents(self.repo)
        self._idle_grace = idle_grace_seconds
        self._clients = 0
        self._idle_task: asyncio.Task[None] | None = None
        self._listener: asyncio.Server | None = None
        self._discovery: Discovery | None = None
        self._token = ""
        self._browser_issued = False
        self._web: WebHome | None = None
        self._port = 0
        self._started = False
        self._closing = False
        self._closed = asyncio.Event()
        self._connections: set[asyncio.Task[None]] = set()
        self._close_task: asyncio.Task[None] | None = None

    @property
    def port(self) -> int:
        """The OS-assigned IPv4 port, available after start()."""
        if not self._port:
            raise RuntimeError("console server has not started")
        return self._port

    async def start(self) -> None:
        if self._started or self._closing:
            raise RuntimeError("console server cannot be restarted")
        importlib.import_module("h11")
        importlib.import_module("websockets.server")
        from .web import WebHome

        self._web = WebHome()
        self._started = True
        try:
            self._discovery = Discovery(self.repo)
            self._discovery.acquire()
            self._listener = await asyncio.start_server(
                self._accept, "127.0.0.1", 0, start_serving=False
            )
            self._port = self._listener.sockets[0].getsockname()[1]
            self._token = secrets.token_hex(32)
            self._discovery.publish(self._port, self._token)
            await self._listener.start_serving()
            self._idle_task = asyncio.create_task(self._exit_when_idle())
        except BaseException:
            await self.close()
            raise

    def _accept(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.create_task(self._handle(reader, writer))
        self._connections.add(task)
        task.add_done_callback(self._connections.discard)

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        import h11

        connection = h11.Connection(h11.SERVER, max_incomplete_event_size=HEADER_LIMIT)
        request: h11.Request | None = None
        handed_off = False
        try:
            prefix = bytearray()
            async with asyncio.timeout(HEADER_TIMEOUT):
                while request is None:
                    event = connection.next_event()
                    if isinstance(event, h11.Request):
                        request = event
                    elif event is h11.NEED_DATA:
                        data = await reader.read(READ_CHUNK)
                        if not data:
                            return
                        prefix.extend(data)
                        connection.receive_data(data)
                    else:
                        return
            # h11 supplies the consumed-byte boundary, including when a body/frame
            # arrives in the same read. Never scan or reconstruct the raw envelope.
            tail, eof = connection.trailing_data
            boundary = len(prefix) - len(tail)
            if boundary > HEADER_LIMIT:
                await self._http(connection, request, reader, writer, 431)
                return
            status = self._admission(request)
            if status is not None:
                await self._http(connection, request, reader, writer, status)
                return
            if request.target != b"/ws":
                status, body, mime, headers = self._page(request)
                await self._http(
                    connection,
                    request,
                    reader,
                    writer,
                    status,
                    body=body,
                    mime=mime,
                    extra_headers=headers,
                )
                return
            if request.method != b"GET":
                await self._http(connection, request, reader, writer, 405)
                return
            if not self._authenticated(request):
                await self._http(connection, request, reader, writer, 401)
                return
            if any(
                name == b"transfer-encoding"
                or (name == b"content-length" and int(value) != 0)
                for name, value in request.headers
            ):
                await self._http(connection, request, reader, writer, 400)
                return
            end = connection.next_event()
            paused = connection.next_event()
            if not isinstance(end, h11.EndOfMessage) or paused is not h11.PAUSED or eof:
                await self._http(connection, request, reader, writer, 400)
                return
            envelope = bytes(prefix[:boundary])
            del prefix
            handed_off = True
            await self._websocket(envelope, tail, reader, writer)
        except h11.RemoteProtocolError as exc:
            await self._http(connection, request, reader, writer, exc.error_status_hint)
        except TimeoutError:
            if not handed_off:
                await self._http(connection, request, reader, writer, 408)
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()
            try:
                async with asyncio.timeout(CLOSE_TIMEOUT):
                    await writer.wait_closed()
            except (TimeoutError, ConnectionError, OSError):
                pass

    def _admission(self, request: h11.Request) -> int | None:
        host = [value for name, value in request.headers if name == b"host"]
        origin = [value for name, value in request.headers if name == b"origin"]
        expected = f"127.0.0.1:{self.port}".encode()
        if host != [expected] or origin not in ([], [b"http://" + expected]):
            return 403
        if request.method not in (b"GET", b"HEAD"):
            return 405
        return None

    def _authenticated(
        self, request: h11.Request, *, browser_page: bool = False
    ) -> bool:
        auth = [value for name, value in request.headers if name == b"authorization"]
        cookies = [value for name, value in request.headers if name == b"cookie"]
        origin = [value for name, value in request.headers if name == b"origin"]
        if len(auth) == 1 and not cookies:
            return secrets.compare_digest(auth[0], b"Bearer " + self._token.encode())
        if (
            len(cookies) == 1
            and not auth
            and (browser_page or origin == [f"http://127.0.0.1:{self.port}".encode()])
        ):
            return secrets.compare_digest(
                cookies[0], b"console_token=" + self._token.encode()
            )
        return False

    def _page(
        self, request: h11.Request
    ) -> PageResponse:
        """Admit a fixed resource and redeem browser bootstrap without an intervening await."""
        rejected: PageResponse = (401, None, "text/plain; charset=utf-8", [])
        missing: PageResponse = (404, None, "text/plain; charset=utf-8", [])
        try:
            url = urlsplit(request.target.decode("ascii"))
            if url.scheme or url.netloc or url.fragment:
                return missing
            query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        except (ValueError, UnicodeError):
            return rejected
        if url.path != "/" and (
            self._web is None or url.path not in self._asset_paths()
        ):
            return missing
        if url.path != "/" and query:
            return missing
        if set(query) - {"token", "lang"} or any(
            len(values) != 1 for values in query.values()
        ):
            return rejected
        language = "ru"
        if "token" in query:
            if not secrets.compare_digest(query["token"][0].encode("utf-8"), self._token.encode()):
                return rejected
            credentials = [
                name
                for name, _ in request.headers
                if name in (b"cookie", b"authorization")
            ]
            authenticated = self._authenticated(request, browser_page=True)
            if credentials and (credentials != [b"cookie"] or not authenticated):
                return rejected
            if not authenticated:
                if self._browser_issued or request.method != b"GET":
                    return rejected
                self._browser_issued = True
                cookie = (
                    f"console_token={self._token}; HttpOnly; SameSite=Strict; Path=/"
                )
                headers = [(b"Set-Cookie", cookie.encode())]
            else:
                headers = []
            headers.append((b"Location", f"/?lang={language}".encode()))
            return 303, b"", "text/plain; charset=utf-8", headers
        if not self._authenticated(request, browser_page=True):
            return rejected
        assert self._web is not None
        if url.path == "/":
            return (
                200,
                self._web.render(self.repo.name, language),
                "text/html; charset=utf-8",
                [],
            )
        asset = self._web.asset(url.path)
        assert asset is not None
        body, mime = asset
        return 200, body, mime, []

    @staticmethod
    def _asset_paths() -> set[str]:
        from .web import ASSETS

        return set(ASSETS)

    async def _http(
        self,
        connection: h11.Connection,
        request: h11.Request | None,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        status: int,
        *,
        body: bytes | None = None,
        mime: str = "text/plain; charset=utf-8",
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        import h11

        if body is None:
            body = b"Request rejected\n"
        security = [
            (name, value)
            for name, value in _SECURITY_HEADERS
            if name != b"Content-Security-Policy"
        ]
        policy = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
            "script-src 'self'; style-src 'self'; img-src 'self'; "
            f"connect-src ws://127.0.0.1:{self.port}; form-action 'self'"
        )
        headers = [
            *security,
            (b"Content-Security-Policy", policy.encode()),
            *(extra_headers or []),
            (b"Content-Type", mime.encode()),
            (b"Content-Length", str(len(body)).encode()),
            (b"Connection", b"close"),
        ]
        if status == 405:
            headers.append((b"Allow", b"GET, HEAD"))
        try:
            async with asyncio.timeout(CLOSE_TIMEOUT):
                writer.write(
                    connection.send(h11.Response(status_code=status, headers=headers))
                )
                if request is None or request.method != b"HEAD":
                    writer.write(connection.send(h11.Data(data=body)))
                writer.write(connection.send(h11.EndOfMessage()))
                await writer.drain()
                if writer.can_write_eof():
                    writer.write_eof()
                # Flush the final response before reading a withheld or large body.
                # h11 drains framing; the application never buffers request bodies.
                while True:
                    event = connection.next_event()
                    if event is h11.NEED_DATA:
                        data = await reader.read(READ_CHUNK)
                        connection.receive_data(data)
                        if not data:
                            break
                    elif event is h11.PAUSED or isinstance(
                        event, (h11.EndOfMessage, h11.ConnectionClosed)
                    ):
                        break
        except (
            TimeoutError,
            ConnectionError,
            OSError,
            h11.RemoteProtocolError,
            h11.LocalProtocolError,
        ):
            pass

    async def _flush_websocket(
        self, protocol: ServerProtocol, writer: asyncio.StreamWriter
    ) -> bool:
        ended = False
        for data in protocol.data_to_send():
            if data:
                writer.write(data)
            else:
                ended = True
        async with asyncio.timeout(CLOSE_TIMEOUT):
            await writer.drain()
        if ended and writer.can_write_eof():
            writer.write_eof()
        return ended

    async def _websocket(
        self,
        envelope: bytes,
        tail: bytes,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        from websockets.http11 import Request
        from websockets.server import ServerProtocol
        from websockets.typing import Origin

        protocol = ServerProtocol(
            origins=[Origin(f"http://127.0.0.1:{self.port}"), None],
            extensions=None,
            subprotocols=None,
            max_size=MESSAGE_LIMIT,
            logger=_PROTOCOL_LOGGER,
        )
        protocol.receive_data(envelope)
        events = protocol.events_received()
        if len(events) != 1 or not isinstance(events[0], Request):
            await self._flush_websocket(protocol, writer)
            return
        response = protocol.accept(events[0])
        if self._closing:
            response = protocol.reject(503, "Console is closing\n")
        protocol.send_response(response)
        if await self._flush_websocket(protocol, writer) or response.status_code != 101:
            return
        if tail:
            protocol.receive_data(tail)
        self._clients += 1
        try:
            await self._pump_websocket(protocol, reader, writer)
        finally:
            self._clients -= 1

    async def _pump_websocket(
        self,
        protocol: ServerProtocol,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        from websockets.frames import Frame, Opcode

        send_lock = asyncio.Lock()
        requests: set[asyncio.Task[None]] = set()
        subscriptions: set[asyncio.Task[None]] = set()
        closing_at: float | None = None
        try:
            while True:
                for event in protocol.events_received():
                    if not isinstance(event, Frame) or protocol.close_expected():
                        continue
                    if event.opcode == Opcode.TEXT and event.fin:
                        try:
                            raw = bytes(event.data).decode("utf-8")
                        except UnicodeDecodeError:
                            protocol.send_close(1007, "Invalid UTF-8")
                            continue
                        job_type = job_request_type(raw)
                        pending, limit = (
                            (subscriptions, MAX_SUBSCRIPTIONS)
                            if job_type == "job.subscribe"
                            or is_orchestration_request(raw)
                            else (requests, MAX_UNFINISHED_REQUESTS)
                        )
                        if len(pending) >= limit:
                            protocol.send_text(busy(raw).encode())
                            continue
                        request = asyncio.create_task(
                            self._answer(raw, job_type, protocol, writer, send_lock)
                        )
                        pending.add(request)
                        request.add_done_callback(pending.discard)
                    elif event.opcode in (Opcode.TEXT, Opcode.BINARY, Opcode.CONT):
                        protocol.send_close(1003, "No application protocol")
                async with send_lock:
                    ended = await self._flush_websocket(protocol, writer)
                if ended:
                    return
                if protocol.close_expected():
                    if closing_at is None:
                        closing_at = asyncio.get_running_loop().time() + CLOSE_TIMEOUT
                    async with asyncio.timeout_at(closing_at):
                        data = await reader.read(READ_CHUNK)
                else:
                    data = await reader.read(READ_CHUNK)
                if not data:
                    protocol.receive_eof()
                    async with send_lock:
                        await self._flush_websocket(protocol, writer)
                    return
                protocol.receive_data(data)
        finally:
            unfinished = requests | subscriptions
            for request in unfinished:
                request.cancel()
            await asyncio.gather(*unfinished, return_exceptions=True)

    async def _answer(
        self,
        raw: str,
        job_type: str | None,
        protocol: ServerProtocol,
        writer: asyncio.StreamWriter,
        send_lock: asyncio.Lock,
    ) -> None:
        """Answer one request frame beside the pump, so a slow check never stalls Ping or Close."""
        try:
            if job_type is not None:
                async with contextlib.aclosing(self._jobs.replies(raw)) as replies:
                    async for reply in replies:
                        if not await self._send_reply(
                            reply, protocol, writer, send_lock
                        ):
                            return
            elif is_orchestration_request(raw):
                async with contextlib.aclosing(self._events.replies(raw)) as replies:
                    async for reply in replies:
                        if not await self._send_reply(
                            reply, protocol, writer, send_lock
                        ):
                            return
            elif is_decisions_request(raw):
                await self._send_reply(
                    await respond_decisions(raw, self._decisions),
                    protocol,
                    writer,
                    send_lock,
                )
            else:
                await self._send_reply(
                    await respond(raw, self._snapshots), protocol, writer, send_lock
                )
        except Exception:
            # A reply that cannot be sent ends the connection; the pump sees the closed stream.
            writer.close()

    async def _send_reply(
        self,
        reply: str,
        protocol: ServerProtocol,
        writer: asyncio.StreamWriter,
        send_lock: asyncio.Lock,
    ) -> bool:
        async with send_lock:
            if protocol.close_expected():
                return False
            protocol.send_text(reply.encode())
            if await self._flush_websocket(protocol, writer):
                writer.close()
                return False
        return True

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
            if self._listener is not None:
                self._listener.close()
                await self._listener.wait_closed()
            tasks = list(self._connections)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
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
