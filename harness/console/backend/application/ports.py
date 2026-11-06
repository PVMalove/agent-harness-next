"""What the console use cases need from the outside world; `backend/composition.py` supplies the
infrastructure that implements each port."""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol

from ....json_types import JsonObject
from ...kernel.batch_history import History
from ...kernel.catalog import Reversibility
from ...kernel.container_route import Authored
from ...kernel.coordinator_api import ApiResult
from ...kernel.home_snapshot import HomeSnapshot
from ...kernel.reports import LedgerView
from ...kernel.protocol import _clip
from ..domain.events import Event, Observation, View
from ..domain.task_board import REASON_BYTES, SpecList, SpecTickets, TrackerSpec
from ..domain.worker_steps import WorkerFacts


class Clock(Protocol):
    """Monotonic seconds."""

    def __call__(self) -> float: ...


class HomeCollector(Protocol):
    """Collect the Home snapshot of a project; blocks until the checks are done."""

    def __call__(self, repo: Path, /) -> HomeSnapshot: ...


class LedgerCollector(Protocol):
    """Read the orchestration ledger of a project for the Reports and Orchestration screens;
    blocks until it is read."""

    def __call__(self, repo: Path, /) -> LedgerView: ...


class LockReader(Protocol):
    """The read-only state of the project's ledger lock; raises when it cannot be read."""

    def __call__(self, repo: Path, /) -> dict[str, object]: ...


class RecoveryReader(Protocol):
    """The batch history and the recovery status of one batch, through read-only coordinator
    commands; blocks until the command ends."""

    def history(self, repo: Path) -> History: ...

    def status(self, repo: Path, batch: str, skip: Sequence[str]) -> ApiResult: ...


class RouteReader(Protocol):
    """The authored orchestration configuration and the read-only `dispatch preflight` of the
    container route; blocks until it is read."""

    def authored(self, repo: Path) -> Authored: ...

    def preflight(
        self, repo: Path, batch: str, role: str, runtime: str
    ) -> ApiResult: ...


class HealthCollector(Protocol):
    """The `harness health --json` report of a project, offline or `online`, for the Diagnostics
    screen; blocks until every check ran and never applies a fix."""

    def __call__(self, repo: Path, online: bool, /) -> JsonObject: ...


class HarnessCollector(Protocol):
    """What the harness installed in a project (`state`), the package version and the drift
    state of the managed files, for the Harness screen; blocks until read and never writes."""

    def __call__(self, repo: Path, /) -> dict[str, object]: ...


class MaintenanceCollector(Protocol):
    """The cleanup plans with their sizes and the worktree facts (`maintenance`, or null with the
    `error` text) for the Harness screen; blocks until read and never deletes."""

    def __call__(self, repo: Path, /) -> dict[str, object]: ...


class RepoMapCollector(Protocol):
    """The Repo Map screen's facts (`RepoMapFacts.to_payload`): HEAD, the map cached for it, the
    tier, the parser bundle, the project languages and the memory status; blocks until read and
    never builds a map or runs the Repo Map CLI."""

    def __call__(self, repo: Path, /) -> dict[str, object]: ...


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


TRACKER_FAILURES = frozenset(
    {
        "not_configured",
        "tool_missing",
        "timeout",
        "auth",
        "failed",
        "bad_output",
        "not_found",
    }
)


class TrackerUnavailable(Exception):
    """The tracker cannot be read now: ``reason`` is one of `TRACKER_FAILURES`, ``message``
    is clipped for the wire."""

    def __init__(self, reason: str, message: str) -> None:
        if reason not in TRACKER_FAILURES:
            raise ValueError(reason)
        clipped = _clip(message, REASON_BYTES)
        super().__init__(clipped)
        self.reason, self.message = reason, clipped


class SpecNotFound(LookupError):
    """The tracker has no open spec with the requested id."""


class TaskBoardReader(Protocol):
    """Read-only tracker facts of the task board; blocks until read and raises
    ``TrackerUnavailable`` or ``SpecNotFound``. Never changes the tracker or local state.
    ``specs`` returns a plain tuple when the source has no listing limit to report."""

    def tracker_type(self, repo: Path) -> str: ...

    def specs(self, repo: Path) -> SpecList | tuple[TrackerSpec, ...]: ...

    def board(self, repo: Path, spec_ref: str) -> SpecTickets: ...


class WorkerFactsReader(Protocol):
    """The dispatch record and its status record, read without the ledger lock; ``None`` when
    the ledger has no such dispatch. Blocks until read and never writes."""

    def __call__(self, repo: Path, dispatch_id: str, /) -> WorkerFacts | None: ...


class StepsLogReader(Protocol):
    """One page of the worker log of ``source`` (``structured`` or ``plain``) from a byte
    offset, whose steps take at most ``budget`` bytes as JSON. Opens the log for reading and stats it
    only; an unusable log is a page with ``state`` ``unavailable`` and a typed ``reason``."""

    def __call__(
        self,
        repo: Path,
        facts: WorkerFacts,
        source: str,
        offset: int,
        budget: int,
        /,
    ) -> Mapping[str, object]: ...
