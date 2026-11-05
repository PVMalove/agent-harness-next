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
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol, cast

from harness.orchestration.ledger.lifecycle import JsonObject

from ..kernel.batch_history import History
from ..kernel.container_route import Authored
from ..kernel.coordinator_api import ApiResult
from ..kernel.discovery import ServerEndpoint
from ..kernel.home_snapshot import HomeSnapshot, Problem, problems_from_text
from ..kernel.protocol import (
    HOME_PROBLEMS_REQUEST,
    HOME_REQUEST,
    LOCK_REQUEST,
    MESSAGE_LIMIT,
    ORCHESTRATION_REQUEST,
    PAGE_REQUEST,
    PROTOCOL_VERSION,
    RECOVERY_REQUEST,
    REPORT_REQUEST,
    REPORTS_REQUEST,
    ROUTE_REQUEST,
    TIMELINE_REQUEST,
)
from ..kernel.reports import (
    BatchTimeline,
    LedgerView,
    ledger_from_payload,
    timeline_from_payload,
)

if TYPE_CHECKING:
    from websockets.sync.client import ClientConnection

OPEN_TIMEOUT = 5.0
# The online checks wait for the network; a reply may take minutes.
REPLY_TIMEOUT = 300.0
CLOSE_TIMEOUT = 1.0
# A running job is polled with `job.get`, never waited on under the connection lock.
JOB_POLL_SECONDS = 0.5


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


class LockUnavailable(ConsoleClientError):
    """The server could not read the ledger lock; the text is its reason."""


class HomeClient(Protocol):
    """What the Home screen needs from the console server."""

    def home(self, *, force: bool = False, online: bool = False) -> HomeSnapshot: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class OrchestrationView:
    """The Orchestration screen's ledger with the ledger lock state or why it is unknown."""

    ledger: LedgerView
    lock: JsonObject | None
    lock_error: str | None


@dataclass(frozen=True)
class RecoveryFacts:
    """The batch history and, for a selected batch, its `recovery status`."""

    history: History
    status: ApiResult | None


@dataclass(frozen=True)
class RouteFacts:
    """The authored configuration and, for a selected batch, its `dispatch preflight`."""

    authored: Authored
    preflight: ApiResult | None


@dataclass(frozen=True)
class JobResult:
    """A finished server job: its phase, exit code, output by channel and error text."""

    phase: str
    returncode: int | None
    stdout: str
    stderr: str
    truncated: bool
    error: str | None


class ScreenClient(HomeClient, Protocol):
    """What the Reports, Orchestration, Recovery and Container route screens need from the
    console server."""

    def reports(self, *, force: bool = False, online: bool = False) -> LedgerView: ...

    def report(self, dispatch_id: str) -> JsonObject | None: ...

    def timeline(self, batch_id: str) -> BatchTimeline | None: ...

    def orchestration(self, *, force: bool = False) -> OrchestrationView: ...

    def ledger_lock(self) -> JsonObject: ...

    def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> RecoveryFacts: ...

    def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> RouteFacts: ...

    def run_job(
        self, command_id: str, values: Mapping[str, str], *, confirmed: bool = False
    ) -> JobResult: ...


def _object(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise MalformedReply(f"{what} сервера консоли не по схеме")
    return cast(dict[str, object], value)


def _lock_of(value: object) -> tuple[JsonObject | None, str | None]:
    found = _object(value, "состояние lock")
    lock, error = found.get("lock"), found.get("error")
    if set(found) != {"lock", "error"} or not (
        (lock is None or isinstance(lock, dict))
        and (error is None or isinstance(error, str))
    ):
        raise MalformedReply("состояние lock сервера консоли не по схеме")
    return cast(JsonObject | None, lock), error


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
        """The Home snapshot with every problem whole; `force` rebuilds the cached one, `online`
        runs the online checks. Problems one reply does not list are read with `home.problems`."""
        with self._lock:
            reply = self._request(
                {"type": HOME_REQUEST, "force": force, "online": online}
            )
            try:
                snapshot = HomeSnapshot.from_payload(reply.get("snapshot"))
            except ValueError:
                raise MalformedReply("snapshot сервера консоли не по схеме") from None
            if "problems_snapshot_id" not in reply:
                return snapshot
            snapshot_id = reply["problems_snapshot_id"]
            if isinstance(snapshot_id, bool) or not isinstance(snapshot_id, int):
                raise MalformedReply("ответ сервера консоли без id списка проблем")
            problems = self._problems(snapshot_id)
        if len(problems) != snapshot.problems_total:
            raise MalformedReply("список проблем сервера консоли неполон")
        return replace(snapshot, problems=problems)

    def reports(self, *, force: bool = False, online: bool = False) -> LedgerView:
        """The ledger of the Reports screen without report bodies; `online` adds the PR
        timings."""
        payload = self._paged({"type": REPORTS_REQUEST, "force": force, "online": online})
        return self._decoded(ledger_from_payload, payload, "леджер")

    def report(self, dispatch_id: str) -> JsonObject | None:
        """The whole body of one completion report; None when the ledger has none."""
        try:
            body = self._paged({"type": REPORT_REQUEST, "dispatch_id": dispatch_id})
        except ServerError as error:
            if error.code == "not_found":
                return None
            raise
        return cast(JsonObject, _object(body, "отчёт"))

    def timeline(self, batch_id: str) -> BatchTimeline | None:
        """The chronology of one batch; None when the ledger has no such batch."""
        try:
            payload = self._paged({"type": TIMELINE_REQUEST, "batch_id": batch_id})
        except ServerError as error:
            if error.code == "not_found":
                return None
            raise
        return self._decoded(timeline_from_payload, payload, "хронология")

    def orchestration(self, *, force: bool = False) -> OrchestrationView:
        """The ledger of the Orchestration screen with the ledger lock state."""
        found = _object(
            self._paged({"type": ORCHESTRATION_REQUEST, "force": force}), "снимок"
        )
        if set(found) != {"ledger", "lock"}:
            raise MalformedReply("снимок оркестрации сервера консоли не по схеме")
        lock, error = _lock_of(found["lock"])
        ledger = self._decoded(ledger_from_payload, found["ledger"], "леджер")
        return OrchestrationView(ledger, lock, error)

    def ledger_lock(self) -> JsonObject:
        """The ledger lock state; `LockUnavailable` carries why the server could not read it."""
        with self._lock:
            reply = self._request({"type": LOCK_REQUEST})
        lock, error = _lock_of({"lock": reply.get("lock"), "error": reply.get("error")})
        if lock is None:
            raise LockUnavailable(error or "состояние не сообщается")
        return lock

    def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> RecoveryFacts:
        """The batch history and, for `batch`, its `recovery status` skipping `skip`."""
        found = _object(
            self._paged(
                {
                    "type": RECOVERY_REQUEST,
                    "batch": batch,
                    "skip": list(skip),
                    "force": force,
                }
            ),
            "снимок восстановления",
        )
        if set(found) != {"history", "status"}:
            raise MalformedReply("снимок восстановления сервера консоли не по схеме")
        history = self._decoded(History.from_payload, found["history"], "история")
        status = found["status"]
        return RecoveryFacts(
            history,
            None
            if status is None
            else self._decoded(ApiResult.from_payload, status, "статус"),
        )

    def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> RouteFacts:
        """The authored configuration and, for `batch`, its `dispatch preflight`."""
        found = _object(
            self._paged(
                {"type": ROUTE_REQUEST, "batch": batch, "role": role, "runtime": runtime}
            ),
            "снимок маршрута",
        )
        if set(found) != {"authored", "preflight"}:
            raise MalformedReply("снимок маршрута сервера консоли не по схеме")
        authored = self._decoded(Authored.from_payload, found["authored"], "конфигурация")
        preflight = found["preflight"]
        return RouteFacts(
            authored,
            None
            if preflight is None
            else self._decoded(ApiResult.from_payload, preflight, "preflight"),
        )

    def run_job(
        self, command_id: str, values: Mapping[str, str], *, confirmed: bool = False
    ) -> JobResult:
        """Start the catalog command `command_id` as a server job and follow it to its end. A
        refused start (for example `confirmation_required`) is a `ServerError` with its code.
        The running job is polled with `job.get` every `JOB_POLL_SECONDS`, one short request at
        a time, so other requests go in between and a quiet job never hits `REPLY_TIMEOUT`."""
        with self._lock:
            job = self._job(
                self._request(
                    {
                        "type": "job.start",
                        "command_id": command_id,
                        "values": dict(values),
                        "confirmed": confirmed,
                        "client": "tui",
                    }
                )
            )
        outputs = [job]
        while not outputs[-1]["done"]:
            time.sleep(JOB_POLL_SECONDS)
            with self._lock:
                outputs.append(
                    self._job(
                        self._request(
                            {
                                "type": "job.get",
                                "job_id": job["id"],
                                "cursor": outputs[-1]["cursor"],
                            }
                        )
                    )
                )
        return self._job_result(outputs)

    @staticmethod
    def _job(reply: dict[str, object]) -> dict[str, object]:
        job = _object(reply.get("job"), "задача")
        if (
            not isinstance(job.get("id"), str)
            or not isinstance(job.get("done"), bool)
            or not isinstance(job.get("output"), list)
            or isinstance(job.get("cursor"), bool)
            or not isinstance(job.get("cursor"), int)
        ):
            raise MalformedReply("задача сервера консоли не по схеме")
        return job

    @staticmethod
    def _job_result(batches: list[dict[str, object]]) -> JobResult:
        streams: dict[str, list[str]] = {"stdout": [], "stderr": []}
        for batch in batches:
            for fragment in cast(list[object], batch["output"]):
                item = _object(fragment, "вывод задачи")
                channel, text = item.get("channel"), item.get("text")
                if not isinstance(channel, str) or channel not in streams:
                    raise MalformedReply("вывод задачи сервера консоли не по схеме")
                if not isinstance(text, str):
                    raise MalformedReply("вывод задачи сервера консоли не по схеме")
                streams[channel].append(text)
        last = batches[-1]
        phase, code, error = last.get("phase"), last.get("returncode"), last.get("error")
        if (
            not isinstance(phase, str)
            or not (code is None or (isinstance(code, int) and not isinstance(code, bool)))
            or not (error is None or isinstance(error, str))
        ):
            raise MalformedReply("итог задачи сервера консоли не по схеме")
        return JobResult(
            phase,
            code,
            "".join(streams["stdout"]),
            "".join(streams["stderr"]),
            any(batch.get("truncated") is True for batch in batches),
            error,
        )

    @staticmethod
    def _decoded[T](decode: Callable[[object], T], payload: object, what: str) -> T:
        try:
            return decode(payload)
        except ValueError:
            raise MalformedReply(f"{what} сервера консоли не по схеме") from None

    def _paged(self, body: dict[str, object]) -> object:
        """The JSON value of a paged snapshot: the first reply, then every `snapshot.page`."""
        with self._lock:
            reply = self._request(body)
            snapshot_id = reply.get("snapshot_id")
            if isinstance(snapshot_id, bool) or not isinstance(snapshot_id, int):
                raise MalformedReply("ответ сервера консоли без id снимка")
            parts: list[str] = []
            offset = 0
            while True:
                text, next_offset, done = _page_of(reply, offset)
                parts.append(text)
                if done:
                    break
                offset = next_offset
                reply = self._request(
                    {"type": PAGE_REQUEST, "snapshot_id": snapshot_id, "offset": offset}
                )
        try:
            return json.loads("".join(parts))
        except (ValueError, RecursionError):
            raise MalformedReply("снимок сервера консоли — не JSON") from None

    def _problems(self, snapshot_id: int) -> tuple[Problem, ...]:
        """Every problem of the served snapshot `snapshot_id`, page by page."""
        parts: list[str] = []
        offset = 0
        while True:
            reply = self._request(
                {
                    "type": HOME_PROBLEMS_REQUEST,
                    "snapshot_id": snapshot_id,
                    "offset": offset,
                }
            )
            text, next_offset, done = (
                reply.get("text"),
                reply.get("next"),
                reply.get("done"),
            )
            if (
                not isinstance(text, str)
                or not isinstance(done, bool)
                or isinstance(next_offset, bool)
                or not isinstance(next_offset, int)
            ):
                raise MalformedReply("страница проблем сервера консоли не по схеме")
            # A page that does not move on would be asked for again forever.
            if not done and next_offset <= offset:
                raise MalformedReply("страница проблем сервера консоли пуста")
            parts.append(text)
            if done:
                break
            offset = next_offset
        try:
            return problems_from_text("".join(parts))
        except ValueError:
            raise MalformedReply("список проблем сервера консоли не по схеме") from None

    def _request(self, body: dict[str, object]) -> dict[str, object]:
        """The successful reply to one request; the caller holds the lock."""
        request_id = self._send(body)
        return self._checked(self._receive(), request_id, str(body["type"]))

    def _send(self, body: dict[str, object]) -> int:
        """Send one request under a new id; the caller holds the lock."""
        from websockets.exceptions import ConnectionClosed

        self._next_id += 1
        try:
            self._connection.send(json.dumps({"id": self._next_id, **body}))
        except ConnectionClosed:
            raise ConnectionLost("соединение с сервером консоли потеряно") from None
        return self._next_id

    @staticmethod
    def _checked(
        reply: dict[str, object], request_id: int, kind: str
    ) -> dict[str, object]:
        """`reply` when it is the successful answer to request `request_id` of type `kind`."""
        if reply.get("v") != PROTOCOL_VERSION:
            raise MalformedReply("ответ сервера консоли другой версии протокола")
        if reply.get("id") != request_id or reply.get("type") != kind:
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
        return reply

    def _receive(self) -> dict[str, object]:
        """The next reply object; the caller holds the lock."""
        from websockets.exceptions import ConnectionClosed

        try:
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


def _page_of(reply: dict[str, object], offset: int) -> tuple[str, int, bool]:
    """The text, next offset and last-page flag of one page that starts at `offset`."""
    text, next_offset, done = reply.get("text"), reply.get("next"), reply.get("done")
    if (
        not isinstance(text, str)
        or not isinstance(done, bool)
        or isinstance(next_offset, bool)
        or not isinstance(next_offset, int)
    ):
        raise MalformedReply("страница снимка сервера консоли не по схеме")
    # A page that does not move on would be asked for again forever.
    if not done and next_offset <= offset:
        raise MalformedReply("страница снимка сервера консоли пуста")
    return text, next_offset, done
