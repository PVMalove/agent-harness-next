"""Screen facts read from the project: the orchestration ledger, the ledger lock, the read-only
coordinator commands of the Recovery and Container route screens (`batch list`, `recovery status`,
`dispatch preflight`), the health report of Diagnostics, the installation, drift and
maintenance facts of Harness, the Repo Map facts and the «Открыть проект» facts. Nothing here
writes, locks the ledger, applies a fix, installs or starts a worker."""

from __future__ import annotations

import argparse
import threading
from collections.abc import Sequence
from pathlib import Path

from ....health.report_json import to_json
from ....json_types import JsonObject
from ....repo_map.bundle_fetch import ParserStatus, parser_status
from ...kernel import data as console_data
from ...kernel.batch_history import History, load_history
from ...kernel.container_route import Authored, read_authored
from ...kernel.coordinator_api import ApiResult, CoordinatorApi
from ...kernel.harness_facts import harness_state
from ...kernel.maintenance import load_maintenance
from ...kernel.open_project_snapshot import Candidate, OpenProjectFacts
from ...kernel.project_target import (
    ProjectTarget,
    capability_options,
    inspect_target,
    installation_blockers,
)
from ...kernel.pr_timings import load_reports_view
from ...kernel.repo_map import cached_map, head_commit
from ...kernel.repo_map_settings import language_files, memory_status, tier_setting
from ...kernel.repo_map_snapshot import RepoMapFacts
from ...kernel.reports import LedgerView, load_ledger_view
from ...kernel.runner import CommandRunner, capturing_runner


def collect_ledger(repo: Path) -> LedgerView:
    """The ledger as the Reports screen reads it, without PR timings."""
    return load_ledger_view(repo)


def collect_ledger_online(repo: Path) -> LedgerView:
    """The ledger with the PR timings of the project's tracker."""
    return load_reports_view(repo)


def read_lock(repo: Path) -> dict[str, object]:
    """The ledger lock without taking it, like `coordinator.py ledger lock-status`."""
    from harness.orchestration.ledger.ledger_admin import ledger_lock_status

    return dict(ledger_lock_status(argparse.Namespace(repo=str(repo), state_dir=None)))


class CoordinatorFacts:
    """The read-only coordinator commands of the Recovery and Container route screens."""

    def __init__(self, runner: CommandRunner = capturing_runner) -> None:
        self._runner = runner

    def _api(self, repo: Path) -> CoordinatorApi:
        return CoordinatorApi(repo, self._runner)

    def history(self, repo: Path) -> History:
        return load_history(self._api(repo))

    def status(self, repo: Path, batch: str, skip: Sequence[str]) -> ApiResult:
        values: dict[str, str | Sequence[str] | bool] = {"batch": batch, "json": True}
        if skip:
            values["skip"] = list(skip)
        return self._api(repo).call(("recovery", "status"), values)

    def authored(self, repo: Path) -> Authored:
        return read_authored(repo)

    def preflight(self, repo: Path, batch: str, role: str, runtime: str) -> ApiResult:
        values = {"batch": batch, "role": role}
        if runtime:
            values["runtime"] = runtime
        return self._api(repo).call(("dispatch", "preflight"), values)


class HealthFacts:
    """The health report of the Diagnostics screen. The checks share process state, so the
    offline and the online report are never collected at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def __call__(self, repo: Path, online: bool, /) -> JsonObject:
        with self._lock:
            return to_json(console_data.collect_diagnostics(repo, online=online))


def harness_facts(repo: Path) -> dict[str, object]:
    """The installed harness, the package version and the drift state (`harness diff --json` in
    a subprocess); a drift that cannot be read is "unknown"."""
    try:
        drift = console_data.drift_state(repo)
    except Exception:  # an unreadable drift is shown as unknown, never as clean
        drift = "unknown"
    return {
        "state": harness_state(repo).to_payload(),
        "package_version": console_data.harness_version(),
        "drift": drift,
    }


def maintenance_facts(repo: Path) -> dict[str, object]:
    """The cleanup plans with their sizes and the worktree facts, or the text of why the plan
    cannot be read."""
    try:
        view = load_maintenance(repo)
    except Exception as exc:  # shown to the operator, never hidden
        return {"maintenance": None, "error": str(exc) or type(exc).__name__}
    return {"maintenance": view.to_payload(), "error": ""}


def repo_map_facts(repo: Path) -> dict[str, object]:
    """HEAD, the map cached for it, the tier, the parser bundle (null when it cannot be read),
    the project languages and the memory status; never runs the Repo Map CLI."""
    head = head_commit(repo)
    try:
        parsers: ParserStatus | None = parser_status(repo)
    except Exception:  # an unreadable bundle is shown as unknown, never as installed
        parsers = None
    return RepoMapFacts(
        head=head,
        view=cached_map(repo, head) if head is not None else None,
        tier=tier_setting(repo),
        memory=memory_status(repo),
        parsers=parsers,
        language_files=language_files(repo),
    ).to_payload()


# «Открыть проект» lists at most this many sibling projects beside the served one.
CANDIDATE_LIMIT = 20


def _installed(path: Path) -> bool:
    return (path / ".harness" / "harness.lock").is_file()


def _candidates(repo: Path) -> tuple[Candidate, ...]:
    """The served project, then the Git projects beside it (a `.git` directory or worktree
    file), by name; an unreadable parent lists only the served project."""
    try:
        siblings = sorted(
            path
            for path in repo.parent.iterdir()
            if path != repo and path.is_dir() and (path / ".git").exists()
        )
    except OSError:
        siblings = []
    return (
        Candidate(str(repo), _installed(repo), True),
        *(
            Candidate(str(path), _installed(path), False)
            for path in siblings[:CANDIDATE_LIMIT]
        ),
    )


def open_project_facts(repo: Path) -> dict[str, object]:
    """The installation state of the served project (the plan target and the blockers of every
    capability, or why it cannot be installed into) and the candidate projects; reads files and
    runs `git rev-parse`, never installs."""
    target: ProjectTarget | None = None
    blockers: dict[str, tuple[str, ...]] = {}
    error = ""
    try:
        target = inspect_target(str(repo))
        blockers = {
            name: installation_blockers(target, name)
            for name, _ in capability_options()
        }
    except ValueError as exc:  # not a Git project, a broken lock: the reason is shown
        target, error = None, str(exc)
    except (
        OSError
    ) as exc:  # unreadable files: the plan stays unchecked, never unblocked
        blockers, error = {}, str(exc) or type(exc).__name__
    return OpenProjectFacts(
        str(repo), target, error, blockers, _candidates(repo)
    ).to_payload()
