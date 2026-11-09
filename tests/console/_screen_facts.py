"""Fake screen facts for the console server tests: an in-memory ledger, a lock reader, the
recovery and container route readers and the Diagnostics, Harness, Repo Map, «Открыть проект» and
«Обновить Harness» and «Настройка» collectors, each counting its calls."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harness.console.backend.application.screens import ScreenService
from harness.console.kernel.batch_history import History, HistoryBatch
from harness.console.kernel.configuration_snapshot import (
    AdapterFacts,
    ConfigFile,
    ConfigurationFacts,
)
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, Outcome
from harness.console.kernel.harness_facts import HarnessState
from harness.console.kernel.open_project_snapshot import Candidate, OpenProjectFacts
from harness.console.kernel.publish_view import GitFacts
from harness.console.kernel.project_target import ProjectTarget
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

CONFIGURATION_FACTS = ConfigurationFacts(
    schema_installed=True,
    orchestration_installed=False,
    transaction_pending=False,
    store_root="/work/project/.harness/config_versions",
    files={
        "project.json": ConfigFile(True, "d" * 64, {"tracker": {"token": "••••••"}}, ""),
        "orchestration.json": ConfigFile(False, "", {"roles": {}}, ""),
    },
    adapters=AdapterFacts(None, "Сначала установите харнесс проекта"),
)

UPDATE_DRIFT: dict[str, object] = {
    "state": "drift",
    "conflict": ["AGENTS.md"],
    "seed_differing": [".harness/project.json"],
}


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
        excluded=2,
    )


def open_project_facts() -> OpenProjectFacts:
    return OpenProjectFacts(
        repo="/work/project",
        target=ProjectTarget(Path("/work/project"), "init", (), (), ()),
        error="",
        blockers={"engineering-suite": ()},
        candidates=(
            Candidate("/work/project", installed=False, current=True),
            Candidate("/work/other", installed=True, current=False),
        ),
    )


class Facts:
    """Every screen port with call counters."""

    def __init__(self) -> None:
        self.calls: dict[str, int] = {}
        self.lock_error: Exception | None = None
        self.collect_error: Exception | None = None
        self.statuses: list[tuple[str, tuple[str, ...]]] = []
        self.preflights: list[tuple[str, str, str]] = []
        self.diffs: list[str] = []

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
            "drift_files": 0,
            "store": {
                "authority": "file-ledger",
                "schema": 3,
                "generation": "generation-1",
                "audit_records": 4,
            },
            "adapters": [
                {"path": ".harness/adapters/a.json", "status": "current", "problem": None}
            ],
        }

    def maintenance(self, repo: Path, /) -> dict[str, object]:
        self._count("maintenance")
        return {"maintenance": None, "error": "Git unavailable"}

    def repo_map(self, repo: Path, /) -> dict[str, object]:
        self._count("repo_map")
        return repo_map_facts().to_payload()

    def open_project(self, repo: Path, /) -> dict[str, object]:
        self._count("open_project")
        return open_project_facts().to_payload()

    def update_harness(self, repo: Path, /) -> dict[str, object]:
        self._count("update_harness")
        return {
            "state": HARNESS_STATE.to_payload(),
            "package_version": "1.0.1",
            "drift": UPDATE_DRIFT,
        }

    def configuration(self, repo: Path, /) -> dict[str, object]:
        self._count("configuration")
        return CONFIGURATION_FACTS.to_payload()

    def update_diff(self, repo: Path, relative: str, /) -> str:
        self.diffs.append(relative)
        return f"--- проект/{relative}\n+++ после обновления/{relative}\n"


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def service(
    facts: Facts,
    clock: Clock | None = None,
    *,
    ttl: float = 15.0,
    publish_git: GitFacts | None = None,
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
        open_project=facts.open_project,
        update_harness=facts.update_harness,
        update_diff=facts.update_diff,
        configuration=facts.configuration,
        publish_git=publish_git,
    )
