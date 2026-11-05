"""What the console use cases need from the outside world; `backend/composition.py` supplies the
infrastructure that implements each port."""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from ...kernel.catalog import Reversibility
from ...kernel.home_snapshot import HomeSnapshot
from ..domain.events import Event, Observation, View


class Clock(Protocol):
    """Monotonic seconds."""

    def __call__(self) -> float: ...


class HomeCollector(Protocol):
    """Collect the Home snapshot of a project; blocks until the checks are done."""

    def __call__(self, repo: Path, /) -> HomeSnapshot: ...


class JobExecutor(Protocol):
    """Emit on the event loop, and finish all output callbacks before returning an exit code.

    A set ``cancel_event`` asks to stop the command and its descendants. The executor raises
    ``CommandCancelled`` only when it stopped a command that was still running; a command that
    already ended returns its own exit code."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        on_output: Callable[[str, str], None],
        cancel_event: threading.Event,
    ) -> Awaitable[int]: ...


class CommandSpec(Protocol):
    """A command a job can run: what `JobService` reads of a catalog entry."""

    @property
    def key(self) -> str: ...

    @property
    def read_only(self) -> bool: ...

    @property
    def reversibility(self) -> Reversibility: ...

    @property
    def needs_confirmation(self) -> bool: ...

    def available(self, repo: Path) -> bool: ...

    def accepts(self, values: Mapping[str, str]) -> bool: ...

    def cli_argv(
        self, repo: Path, values: Mapping[str, str] | None = None
    ) -> list[str]: ...


class CommandJournal(Protocol):
    """Append one finished job's record to the project's command journal; raises `OSError`,
    `ValueError` or `subprocess.SubprocessError` when it cannot."""

    def __call__(self, repo: Path, record: Mapping[str, object]) -> None: ...


class IdSource(Protocol):
    """A new unique job id."""

    def __call__(self) -> str: ...


class WallClock(Protocol):
    """The current UTC time as an ISO 8601 string."""

    def __call__(self) -> str: ...


class SourceUnavailable(Exception):
    """The orchestration source cannot be read as a whole: ``reason`` is ``missing``,
    ``unreadable`` or ``runtime_unavailable``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason, self.message = reason, message


class OrchestrationReader(Protocol):
    """Runs in a thread and raises ``SourceUnavailable``."""

    def read(self) -> Observation: ...


class JournalUnavailable(Exception):
    """The event journal cannot be read or written."""


class EventJournal(Protocol):
    """The durable journal of orchestration events. ``load``, ``write`` and ``rewrite`` do file
    work, run in a thread and raise ``JournalUnavailable``; the rest runs on the event loop."""

    @property
    def journal_id(self) -> str: ...

    @property
    def head(self) -> int: ...

    @property
    def floor(self) -> int: ...

    @property
    def view(self) -> View | None: ...

    def load(self) -> None: ...

    def events_after(self, seq: int, limit: int) -> list[Event]: ...

    def record(self, events: list[Event], view: View) -> bytes | None: ...

    def write(self, line: bytes) -> None: ...

    def accept(self, events: list[Event], view: View) -> None: ...

    def needs_compaction(self) -> bool: ...

    def checkpoint(self) -> dict[str, object]: ...

    def rewrite(self, header: dict[str, object]) -> None: ...

    def compacted(self) -> None: ...

    def close(self) -> None: ...


class OpenJournal(Protocol):
    """The project's event journal, not loaded yet; runs in a thread."""

    def __call__(self) -> EventJournal: ...
