"""Fake screen facts for the console server tests: an in-memory ledger, a lock reader, the
recovery and container route readers and the Diagnostics, Harness and Repo Map collectors, each
counting its calls."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harness.console.backend.application.screens import ScreenService
from harness.console.kernel.batch_history import History, HistoryBatch
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, Outcome
from harness.console.kernel.harness_facts import HarnessState
from harness.console.kernel.repo_map import parse_map
from harness.console.kernel.repo_map_settings import MemoryStatus, TierSetting
from harness.console.kernel.repo_map_snapshot import RepoMapFacts
from harness.console.kernel.reports import (
    BatchSummary,
    LedgerView,
    ReportEntry,
    StageEntry,
)
from harness.health.model import CheckResult, JsonObject, Report
from harness.health.report_json import to_json
from harness.repo_map.bundle_fetch import ParserStatus

from ._console_repo_map_fixture import map_payload

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


def health_report(online: bool = False) -> Report:
    return Report(
        1,
        "/work/project",
        online,
        [CheckResult("core.lock", "core", "fail", "нет lock")],
    )


HARNESS_STATE = HarnessState(True, "1.0.0", ("engineering-suite",), 3, 7, "t", True)

HEAD = "a" * 40


def repo_map_facts() -> RepoMapFacts:
    view = parse_map(map_payload(HEAD), origin="кэш")
    assert not isinstance(view, str)
    return RepoMapFacts(
        head=HEAD,
        view=view,
        tier=TierSetting("full", True),
        memory=MemoryStatus(True, True, ("adr",), 4, top_k=5, max_tokens=1000),
        parsers=ParserStatus(
            Path("/work/project/registry"), "cp312-linux", "bundle", ("python",), None
        ),
        language_files={"python": 3},
    )


class Facts:
    """Every screen port with call counters."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.lock_error: Exception | None = None
        self.collect_error: Exception | None = None
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


    def health(self, repo: Path, online: bool, /) -> JsonObject:
        self._count("health_online" if online else "health")
        if self.collect_error is not None:
            raise self.collect_error
        return to_json(health_report(online))

    def harness(self, repo: Path, /) -> dict[str, object]:
        self._count("harness")
        return {
            "state": HARNESS_STATE.to_payload(),
            "package_version": "1.0.1",
            "drift": "clean",
        }

    def maintenance(self, repo: Path, /) -> dict[str, object]:
        self._count("maintenance")
        return {"maintenance": None, "error": "Git unavailable"}

    def repo_map(self, repo: Path, /) -> dict[str, object]:
        self._count("repo_map")
        return repo_map_facts().to_payload()


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
        health=facts.health,
        harness=facts.harness,
        maintenance=facts.maintenance,
        repo_map=facts.repo_map,
    )
