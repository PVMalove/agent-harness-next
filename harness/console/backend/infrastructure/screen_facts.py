"""Screen facts read from the project: the orchestration ledger, the ledger lock, the read-only
coordinator commands of the Recovery and Container route screens (`batch list`, `recovery status`,
`dispatch preflight`), the health report of Diagnostics, the installation, drift and
maintenance facts of Harness, the Repo Map facts, the «Открыть проект» facts and the drift and
update diff of «Обновить Harness» and the masked configuration of «Настройка». Nothing here writes, locks the ledger, applies a fix, installs,
updates or starts a worker."""

from __future__ import annotations

import argparse
import shutil
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from ....health.report_json import to_json
from ....json_types import JsonObject
from ....repo_map.bundle_fetch import ParserStatus, parser_status
from ....storage import storage_root
from ...kernel import data as console_data
from ...kernel.batch_history import History, load_history
from ...kernel.configuration_snapshot import collect_configuration
from ...kernel.configuration_wizard import wizard_parameters
from ...kernel.container_inventory import configured_engine, container_inventory
from ...kernel.container_route import Authored, read_authored
from ...kernel.coordinator_api import ApiResult, CoordinatorApi
from ...kernel.harness_facts import harness_state
from ...kernel.home_snapshot import StoreFacts
from ...kernel.maintenance import load_maintenance
from ...kernel.open_project_snapshot import Candidate, OpenProjectFacts
from ...kernel.project_target import (
    ProjectTarget,
    capability_options,
    inspect_target,
    installation_blockers,
)
from ...kernel.pr_timings import load_reports_view
from ...kernel.repo_map import cached_map, head_commit, latest_cached_map
from ...kernel.repo_map_coverage import excluded_files
from ...kernel.repo_map_settings import language_files, memory_status, tier_setting
from ...kernel.repo_map_snapshot import RepoMapFacts
from ...kernel.reports import LedgerView, load_ledger_view
from ...kernel.runner import CommandRunner, capturing_runner
from ...kernel.update_harness_snapshot import UpdateHarnessFacts
from ....health.project_tracker import ProjectTracker, resolve_project_tracker
from ....orchestration.ledger.lifecycle import STORE_LEDGER_VERSION
from ....orchestration.runtime_client import RuntimeClient, RuntimeClientError
from .home_facts import RUNTIME_DOWN, RUNTIME_TIMEOUT_SECONDS, runtime_reason, store_facts


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


def adapter_facts(repo: Path) -> list[dict[str, object]] | None:
    """The runtime adapter files of the installed capabilities with their status (current,
    outdated, missing) and problem; None when the lock or the package cannot be read."""
    try:
        from harness.bin.harness import load_lock, package_files
        from harness.runtime_adapters import adapter_statuses

        lock = load_lock(repo)
        if lock is None:
            return None
        selected = list(lock.get("capabilities") or [])
        statuses = adapter_statuses(
            repo, package_files(selected), lock.get("files") or {}
        )
    except (Exception, SystemExit):  # an unreadable adapter set is unknown, never current
        return None
    return [dict(status) for status in statuses]


def container_facts(repo: Path) -> dict[str, object]:
    """The read-only inventory of the container engine the project's access policy names."""
    return container_inventory(configured_engine(storage_root(repo))).to_payload()


RevisionRead = Callable[[], "int | None"]


def _read_revision(repo: Path) -> RevisionRead:
    """One empty `state.read` of the project's running runtime (2 s): its store revision. The
    runtime is never started; no snapshot is opened."""

    def read() -> int | None:
        reply = RuntimeClient(repo).call(
            "state.read",
            operation_id=f"console-state.read-{uuid.uuid4().hex}",
            payload={"collections": [], "paths": []},
            timeout_seconds=RUNTIME_TIMEOUT_SECONDS,
        )
        return reply.revision

    return read


def runtime_status(repo: Path, *, read: RevisionRead | None = None) -> dict[str, object]:
    """Whether the runtime answers, with its store revision, or why it does not (`read`
    replaces the probe in tests)."""
    try:
        revision = (read or _read_revision(repo))()
    except (RuntimeClientError, OSError, ValueError) as error:
        reason = runtime_reason(error)
    else:
        return {"state": "online", "revision": revision, "reason": ""}
    return {"state": "offline", "revision": None, "reason": reason}


def _runtime_after(repo: Path, store: StoreFacts) -> dict[str, object]:
    """The runtime status after the store facts: a runtime-store probe that got no answer already
    waited its 2 s, so the status reuses that reason instead of a second probe; a cold snapshot
    waits for one probe at most."""
    if store.authority == "runtime-store" and store.reason.startswith(RUNTIME_DOWN.split("{")[0]):
        return {"state": "offline", "revision": None, "reason": store.reason}
    return runtime_status(repo)


# The runtime adapters of the Harness page: (name, adapter file marker, CLI on PATH).
_RUNTIMES = (("Claude Code", "claude", "claude"), ("Codex", "codex", "codex"))
_TRACKERS = {"github": ("GitHub", "gh"), "gitlab": ("GitLab", "glab"), "local": ("Local", None)}


def _runtime_adapter_status(files: list[dict[str, object]]) -> str:
    if not files:
        return "missing"
    return "current" if all(item.get("status") == "current" for item in files) else "outdated"


def integration_facts(
    adapters: list[dict[str, object]] | None,
    tracker: ProjectTracker,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> list[dict[str, object]]:
    """Claude Code and Codex (their adapter files of the installed capabilities and the CLI on
    PATH) and the project tracker (its CLI on PATH); nothing is run and nothing goes online."""
    found: list[dict[str, object]] = []
    for name, marker, cli in _RUNTIMES:
        files = [item for item in adapters or [] if marker in str(item.get("path", "")).lower()]
        found.append(
            {
                "name": name,
                "kind": "runtime",
                "status": "unknown" if adapters is None else _runtime_adapter_status(files),
                "cli": which(cli) is not None,
                "detail": ", ".join(str(item.get("path", "")) for item in files),
            }
        )
    title, tool = _TRACKERS.get(tracker.type, (tracker.type, None))
    present = None if tool is None else which(tool) is not None
    found.append(
        {
            "name": title,
            "kind": "tracker",
            "status": "missing" if present is False else "current",
            "cli": present,
            "detail": "/".join(part for part in (tracker.host, tracker.project) if part),
        }
    )
    return found


def _integrations(repo: Path, adapters: list[dict[str, object]] | None) -> list[dict[str, object]] | None:
    try:
        tracker = resolve_project_tracker(repo).effective
    except (OSError, ValueError):  # an unreadable tracker config: the adapters stay unknown
        return None
    return integration_facts(adapters, tracker)


def harness_facts(repo: Path) -> dict[str, object]:
    """The installed harness, the package version, the drift state and file count (`harness diff
    --json` in a subprocess), the state store, the runtime adapters and the read-only inventory of
    the configured container engine; a drift that cannot be read is "unknown" with a null
    count."""
    try:
        report = console_data.drift_report(repo)
    except Exception:  # an unreadable drift is shown as unknown, never as clean
        report = None
    drift = "unknown"
    drift_files: int | None = None
    if report is not None:
        state = report.get("state")
        drift = state if isinstance(state, str) else "unknown"
        counts = console_data.drift_counts(report) or ()
        drift_files = sum(count for _kind, count in counts)
    adapters = adapter_facts(repo)
    store = store_facts(repo)
    return {
        "state": harness_state(repo).to_payload(),
        "package_version": console_data.harness_version(),
        "drift": drift,
        "drift_files": drift_files,
        "store": asdict(store),
        "adapters": adapters,
        "integrations": _integrations(repo, adapters),
        "runtime": _runtime_after(repo, store),
        "containers": container_facts(repo),
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
    the latest cached map of another commit when HEAD has none (stale for HEAD),
    the project languages, the memory status and the tracked files the map leaves out
    (`git ls-tree`, read-only); never runs the Repo Map CLI."""
    head = head_commit(repo)
    view = cached_map(repo, head) if head is not None else None
    try:
        parsers: ParserStatus | None = parser_status(repo)
    except Exception:  # an unreadable bundle is shown as unknown, never as installed
        parsers = None
    return RepoMapFacts(
        head=head,
        view=view,
        tier=tier_setting(repo),
        memory=memory_status(repo),
        parsers=parsers,
        language_files=language_files(repo),
        excluded=excluded_files(repo, view) if view is not None else None,
        stale=latest_cached_map(repo, exclude=head) if head is not None and view is None else None,
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


def update_harness_facts(repo: Path) -> dict[str, object]:
    """The installed harness, the package version and the `harness diff --json` report (in a
    subprocess); a project without the harness is never diffed, and an unreadable report is
    null. The runtime-store facts and the ledger schema an update migrates to fill the
    migration panel; reading them never migrates anything."""
    state = harness_state(repo)
    drift = console_data.drift_report(repo) if state.installed else None
    return UpdateHarnessFacts(
        state,
        console_data.harness_version(),
        drift,
        store=store_facts(repo),
        store_target_schema=STORE_LEDGER_VERSION,
    ).to_payload()


def update_diff(repo: Path, relative: str) -> str:
    """The unified diff of `relative` against what `harness update` writes there."""
    return console_data.update_diff_text(repo, relative)


def configuration_facts(repo: Path) -> dict[str, object]:
    """The masked configuration files with their digests, a pending transaction and the runtime
    adapter preview with the Settings wizard parameter catalog; never writes or recovers."""
    return {**collect_configuration(repo).to_payload(), "wizard": wizard_parameters(repo)}
