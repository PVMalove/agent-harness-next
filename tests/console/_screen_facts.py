"""Fake screen facts for the console server tests: an in-memory ledger, a lock reader and the
recovery and container route readers, each counting its calls."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harness.console.backend.application.screens import ScreenService
from harness.console.kernel.batch_history import History, HistoryBatch
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, Outcome
from harness.console.kernel.reports import (
    BatchSummary,
    LedgerView,
    ReportEntry,
    StageEntry,
)

BODY = "результат " * 20000  # far above one WebSocket message


def ledger(body: str = BODY) -> LedgerView:
    report = ReportEntry(
        "d-1", "b-1", "#1", "developer", "completed", "t1", {"output": body}
    )
    view = LedgerView(
        reports=[report],
        batches=[BatchSummary("b-1", "#1", "active", "t0")],
        _dispatches={"d-1": {"role": "developer"}},
        _batch_records={"b-1": {"batch_id": "b-1", "ticket": "#1", "state": "active"}},
    )
    view.stages.append(
        StageEntry("d-1", "b-1", "#1", "developer", "reported", "t1", report)
    )
    return view


class Facts:
    """Every screen port with call counters."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.lock_error: Exception | None = None
        self.statuses: list[tuple[str, tuple[str, ...]]] = []
        self.preflights: list[tuple[str, str, str]] = []

    def _count(self, name: str) -> None:
        self.calls[name] = self.calls.get(name, 0) + 1

    def ledger(self, repo: Path, /) -> LedgerView:
        self._count("ledger")
        return ledger()

    def ledger_online(self, repo: Path, /) -> LedgerView:
        self._count("ledger_online")
        return ledger("online")

    def lock(self, repo: Path, /) -> dict[str, object]:
        self._count("lock")
        if self.lock_error is not None:
            raise self.lock_error
        return {"locked": False}

    def history(self, repo: Path) -> History:
        self._count("history")
        return History(
            (HistoryBatch("b-1", "#1", "br", "active", "t0", False, 1, 0, ""),)
        )

    def status(self, repo: Path, batch: str, skip: Sequence[str]) -> ApiResult:
        self.statuses.append((batch, tuple(skip)))
        return ApiResult(Outcome.DOCUMENT, ("status",), ({"batch_id": batch},), 0)

    def authored(self, repo: Path) -> Authored:
        return Authored({"roles": {}})

    def preflight(self, repo: Path, batch: str, role: str, runtime: str) -> ApiResult:
        self.preflights.append((batch, role, runtime))
        return ApiResult(Outcome.REFUSED, ("preflight",), ({"verified": False},), 2)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def service(
    facts: Facts, clock: Clock | None = None, *, ttl: float = 15.0
) -> ScreenService:
    return ScreenService(
        Path("/work/project"),
        ttl=ttl,
        clock=clock or Clock(),
        ledger=facts.ledger,
        ledger_online=facts.ledger_online,
        lock=facts.lock,
        recovery=facts,
        route=facts,
    )
