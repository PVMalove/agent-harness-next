"""The default job executor: the catalog command in a subprocess through the console runner."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from ...kernel.runner import capturing_runner


async def run_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    on_output: Callable[[str, str], None],
    cancel_event: threading.Event,
) -> int:
    loop = asyncio.get_running_loop()

    def emit(channel: str, text: str) -> None:
        loop.call_soon_threadsafe(on_output, channel, text)

    result = await asyncio.to_thread(
        capturing_runner, argv, cwd=cwd, on_output=emit, cancel_event=cancel_event
    )
    return result.returncode
