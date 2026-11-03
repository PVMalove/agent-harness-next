"""The TUI side of the console server (ADR 0028): one WebSocket connection to the project's server,
found through its discovery record and authenticated with its token.

The client is synchronous: requests go one at a time over one connection, and the websockets
background thread answers pings in between, so an open connection also keeps the server from its
idle exit. Every failure is a `ConsoleClientError`; its text is the reason the fallback line shows
and never contains the token. `websockets` is imported inside `connect` only, so the module imports
without the transport dependencies."""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Protocol

from .discovery import ServerEndpoint
from .snapshots import HOME_REQUEST, PROTOCOL_VERSION, HomeSnapshot

if TYPE_CHECKING:
    from websockets.sync.client import ClientConnection

OPEN_TIMEOUT = 5.0
# The online checks wait for the network; a reply may take minutes.
REPLY_TIMEOUT = 300.0
CLOSE_TIMEOUT = 1.0


class ConsoleClientError(Exception):
    """Any failure to get an answer from the console server."""


class ServerUnavailable(ConsoleClientError):
    """No server to talk to: no discovery record, a closed port, a timeout or a refused handshake."""


class TokenRejected(ConsoleClientError):
    """The server refused the discovery token (HTTP 401 on the handshake)."""


class ConnectionLost(ConsoleClientError):
    """The connection closed, or the server did not answer in time."""


class MalformedReply(ConsoleClientError):
    """A reply outside the protocol: not JSON, a binary frame, another version, id or type."""


class ServerError(ConsoleClientError):
    """The server answered the request with an error reply."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"сервер консоли ответил ошибкой {code}: {message}")
        self.code, self.message = code, message


class HomeClient(Protocol):
    """What the Home screen needs from the console server."""

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot: ...

    def close(self) -> None: ...


class ConsoleClient:
    """One open connection to a console server."""

    def __init__(self, connection: ClientConnection) -> None:
        self._connection = connection
        self._lock = threading.Lock()
        self._next_id = 0

    @classmethod
    def connect(
        cls, endpoint: ServerEndpoint, *, open_timeout: float = OPEN_TIMEOUT
    ) -> ConsoleClient:
        """Open the connection to the server at `endpoint`; raises `ServerUnavailable` or
        `TokenRejected`."""
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import connect

        # Here, not at the top: the server module imports the catalog, which imports the launcher.
        from .server import MESSAGE_LIMIT

        try:
            connection = connect(
                f"ws://127.0.0.1:{endpoint.port}/ws",
                proxy=None,
                compression=None,
                origin=None,
                max_size=MESSAGE_LIMIT,
                additional_headers={"Authorization": "Bearer " + endpoint.token},
                open_timeout=open_timeout,
                close_timeout=CLOSE_TIMEOUT,
                legacy=True,
            )
        except InvalidStatus as refused:
            status = refused.response.status_code
            if status == 401:
                raise TokenRejected("сервер консоли не принял токен") from None
            raise ServerUnavailable(
                f"сервер консоли отклонил подключение (HTTP {status})"
            ) from None
        except (OSError, TimeoutError) as exc:
            raise ServerUnavailable(
                f"сервер консоли недоступен ({type(exc).__name__})"
            ) from None
        except Exception as exc:
            # Any other handshake failure (InvalidHandshake and its kin) is no server to talk to.
            raise ServerUnavailable(
                f"сервер консоли не завершил подключение ({type(exc).__name__})"
            ) from None
        return cls(connection)

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot:
        """The Home snapshot; `force` rebuilds the cached one, `online` runs the online checks."""
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            reply = self._exchange(
                {
                    "id": request_id,
                    "type": HOME_REQUEST,
                    "force": force,
                    "online": online,
                }
            )
        if reply.get("v") != PROTOCOL_VERSION:
            raise MalformedReply("ответ сервера консоли другой версии протокола")
        if reply.get("id") != request_id or reply.get("type") != HOME_REQUEST:
            raise MalformedReply("ответ сервера консоли не на этот запрос")
        ok = reply.get("ok")
        if ok is False:
            error = reply.get("error")
            if not isinstance(error, dict):
                raise MalformedReply("ошибка сервера консоли без описания")
            code, message = error.get("code"), error.get("message")
            if not isinstance(code, str) or not isinstance(message, str):
                raise MalformedReply("ошибка сервера консоли без описания")
            raise ServerError(code, message)
        if ok is not True:
            raise MalformedReply("ответ сервера консоли без признака ok")
        try:
            return HomeSnapshot.from_payload(reply.get("snapshot"))
        except ValueError:
            raise MalformedReply("snapshot сервера консоли не по схеме") from None

    def _exchange(self, request: dict[str, object]) -> dict[str, object]:
        from websockets.exceptions import ConnectionClosed

        try:
            self._connection.send(json.dumps(request))
            raw = self._connection.recv(timeout=REPLY_TIMEOUT)
        except ConnectionClosed:
            raise ConnectionLost("соединение с сервером консоли потеряно") from None
        except TimeoutError:
            # A late reply would answer the next request: the connection cannot be reused.
            self.close()
            raise ConnectionLost("сервер консоли не ответил вовремя") from None
        if not isinstance(raw, str):
            raise MalformedReply("сервер консоли прислал двоичный кадр")
        try:
            reply = json.loads(raw)
        except ValueError:
            raise MalformedReply("ответ сервера консоли — не JSON") from None
        if not isinstance(reply, dict):
            raise MalformedReply("ответ сервера консоли — не объект")
        return reply

    def close(self) -> None:
        """Close the connection; closing twice is harmless."""
        self._connection.close()
