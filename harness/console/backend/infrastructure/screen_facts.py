"""Screen facts read from the project: the orchestration ledger, the ledger lock, the read-only
coordinator commands of the Recovery and Container route screens (`batch list`, `recovery status`,
`dispatch preflight`), the health report of Diagnostics and the installation, drift and
maintenance facts of Harness. Nothing here writes, locks the ledger, applies a fix or starts a
worker."""

from __future__ import annotations

import argparse
import threading
from collections.abc import Sequence
from pathlib import Path

from ....health.report_json import to_json
from ....json_types import JsonObject
from ...kernel import data as console_data
from ...kernel.batch_history import History, load_history
from ...kernel.container_route import Authored, read_authored
from ...kernel.coordinator_api import ApiResult, CoordinatorApi
from ...kernel.harness_facts import harness_state
from ...kernel.maintenance import load_maintenance
from ...kernel.pr_timings import load_reports_view
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
