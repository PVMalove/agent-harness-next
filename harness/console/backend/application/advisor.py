"""The AI advice use case of «Настройка»: a CLI check and one bounded, cancellable advice request
at a time per connection, run off the event loop; nothing is cached and nothing is written."""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Mapping

from ...kernel.configuration_advisor import FALLBACK
from ...kernel.protocol import ADVICE_TIMEOUT_SECONDS, CHECK_TIMEOUT_SECONDS
from .ports import AdvisorPort

# Two CLI processes at most run for the whole server, whatever the number of connections.
MAX_RUNNING_ASKS = 2
TIMEOUT_REASON = "CLI не ответил вовремя." + FALLBACK
CANCELLED_REASON = "Запрос ИИ отменён." + FALLBACK


class AdvisorBusy(Exception):
    """Too many advice requests are running."""


def _fallback(cause: str, reason: str) -> dict[str, object]:
    return {"outcome": "fallback", "cause": cause, "reason": reason}


class AdvisorService:
    """Bounds every call: a timeout or a cancel sets the call's Event, which stops the CLI."""

    def __init__(
        self,
        port: AdvisorPort,
        *,
        timeout: float = ADVICE_TIMEOUT_SECONDS,
        check_timeout: float = CHECK_TIMEOUT_SECONDS,
    ) -> None:
        self._port = port
        self._timeout = timeout
        self._check_timeout = check_timeout
        self._running = 0

    async def _bounded(
        self,
        task: asyncio.Future[Mapping[str, object]],
        cancel: threading.Event,
        timeout: float,
    ) -> Mapping[str, object] | None:
        """The result of `task`, or None after `timeout`; cancelling the caller stops it too."""
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout)
        except TimeoutError:
            cancel.set()
            with contextlib.suppress(Exception):
                await task
            return None
        finally:
            if not task.done():
                cancel.set()

    async def check(self, provider: str) -> Mapping[str, object]:
        cancel = threading.Event()
        task = asyncio.ensure_future(
            asyncio.to_thread(self._port.check, provider, cancel)
        )
        status = await self._bounded(task, cancel, self._check_timeout)
        if status is None:
            return {
                "provider": provider,
                "found": True,
                "version_supported": None,
                "authorized": None,
                "ready": False,
                "message": TIMEOUT_REASON,
            }
        return status

    async def ask(
        self,
        provider: str,
        file: str,
        path: tuple[str, ...],
        cancel: threading.Event,
    ) -> Mapping[str, object]:
        """The advice or a fallback; raises `AdvisorBusy` or the port's `AdviceNotFound`."""
        if self._running >= MAX_RUNNING_ASKS:
            raise AdvisorBusy()
        self._running += 1
        try:
            task = asyncio.ensure_future(
                asyncio.to_thread(self._port.ask, provider, file, path, cancel)
            )
            answer = await self._bounded(task, cancel, self._timeout)
        finally:
            self._running -= 1
        if answer is None:
            return _fallback("timeout", TIMEOUT_REASON)
        if cancel.is_set():
            return _fallback("cancelled", CANCELLED_REASON)
        return answer
