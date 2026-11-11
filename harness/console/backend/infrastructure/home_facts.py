"""Home facts read from the project: the dashboard checks and the context cards."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from harness.health.project_tracker import resolve_project_tracker
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError
from harness.orchestration.ledger.lifecycle import (
    POINTER_NAME,
    STORE_LEDGER_VERSION,
    LifecycleLedger,
)

from ...kernel.brand import current_branch, project_commit
from ...kernel.data import DashboardData, collect_dashboard
from ...kernel.harness_facts import harness_state
from ...kernel.project_target import capability_options
from ...kernel.home_snapshot import (
    RECENT_SESSIONS_LIMIT,
    HarnessInstall,
    HomeContext,
    HomeSnapshot,
    ProjectFacts,
    RecentSession,
    RouteStep,
    StoreFacts,
    build_home_snapshot,
)
from ...kernel.reports import LedgerView, load_ledger_view
from ...kernel.repo_map import cached_map, head_commit, latest_cached_map
from ...kernel.repo_map_settings import memory_status


def project_facts(repo: Path) -> ProjectFacts:
    """The repository name, branch, short HEAD and resolved tracker type; reads no network."""
    try:
        tracker: str = resolve_project_tracker(repo).effective.type
    except Exception:  # an unreadable tracker is shown as unknown, never guessed
        tracker = ""
    return ProjectFacts(
        name=repo.resolve().name,
        branch=current_branch(repo),
        commit=project_commit(repo),
        tracker=tracker,
    )


def harness_install(repo: Path) -> HarnessInstall:
    state = harness_state(repo)
    catalog = {name for name, _ in capability_options()}
    return HarnessInstall(
        installed=state.installed,
        installed_version=state.installed_version,
        capabilities=len(state.capabilities),
        skills=state.skills,
        managed_files=state.managed_files,
        capability_names=tuple(state.capabilities),
        uncatalogued=tuple(name for name in state.capabilities if name not in catalog),
    )


# The authority record the runtime writes beside `ledger.json` at the cutover
# (native/harness-runtime/crates/state/src/authority.rs, AUTHORITY_NAME).
AUTHORITY_NAME = "AUTHORITY.json"
RuntimeCall = Callable[[str, dict[str, object]], dict[str, object]]
RUNTIME_TIMEOUT_SECONDS = 2.0
# Why the runtime gave no fact: one text per runtime error code, and one per local failure class,
# so every reason has an English entry in kernel/i18n_strings.py (an exception's own type name is
# never shown).
RUNTIME_DOWN = "runtime не отвечает ({cause})"
NO_AUDIT_COUNT = "runtime не сообщил число записей аудита"


def runtime_reason(error: Exception) -> str:
    """The reason text for a runtime probe that failed with `error`."""
    if isinstance(error, RuntimeClientError):
        cause = error.code
    elif isinstance(error, OSError):
        cause = "ошибка ввода-вывода"
    else:
        cause = "неразборчивый ответ"
    return RUNTIME_DOWN.format(cause=cause)


def _runtime_call(repo: Path) -> RuntimeCall:
    """One bounded request to the project's running runtime; the runtime is never started."""

    def call(operation: str, payload: dict[str, object]) -> dict[str, object]:
        reply = RuntimeClient(repo).call(
            operation,
            operation_id=f"console-{operation}-{uuid.uuid4().hex}",
            payload=cast(JsonObject, payload),
            timeout_seconds=RUNTIME_TIMEOUT_SECONDS,
        )
        return cast(dict[str, object], reply.result)

    return call


def _cutover_at(root: Path) -> str | None:
    """`cutover_at` of `AUTHORITY.json`, written by the runtime at the cutover; None before it."""
    try:
        authority = json.loads((root / AUTHORITY_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = authority.get("cutover_at") if isinstance(authority, dict) else None
    return value if isinstance(value, str) and value else None


def store_facts(repo: Path, *, runtime: RuntimeCall | None = None) -> StoreFacts:
    """The state authority read from `ledger.json` and the selected generation without the ledger
    lock. In the runtime-store epoch the audit count comes from the incremental `state.validate`
    of the running runtime (2 s, `runtime` replaces the client in tests) and the cutover time from
    `AUTHORITY.json`; a runtime that does not answer leaves the count None with its reason."""
    root = repo / STATE_REL
    try:
        pointer = json.loads((root / POINTER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return StoreFacts("none", None, None, None)
    if not isinstance(pointer, dict):
        return StoreFacts("none", None, None, None)
    version = pointer.get("version")
    schema = version if isinstance(version, int) and not isinstance(version, bool) else None
    generation = pointer.get("generation")
    if schema == STORE_LEDGER_VERSION:
        audit_records: int | None = None
        reason = ""
        try:
            result = (runtime or _runtime_call(repo))("state.validate", {"full": False})
            count = result.get("audit_records")
            if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                audit_records = count
            else:
                reason = NO_AUDIT_COUNT
        except (RuntimeClientError, OSError, ValueError) as error:
            reason = runtime_reason(error)
        return StoreFacts(
            "runtime-store",
            schema,
            generation if isinstance(generation, str) else None,
            audit_records,
            cutover_at=_cutover_at(root),
            reason=reason,
        )
    records = LifecycleLedger(root).records_root_lenient()
    audit = records / "audit" if records is not None else None
    return StoreFacts(
        authority="file-ledger",
        schema=schema,
        generation=generation if isinstance(generation, str) else None,
        audit_records=(
            sum(1 for _ in audit.glob("*.json"))
            if audit is not None and audit.is_dir()
            else None
        ),
    )


def recent_sessions(view: LedgerView) -> tuple[RecentSession, ...]:
    """The newest batches with the roles and states of their dispatches in dispatch order."""
    sessions: list[RecentSession] = []
    for batch in view.batches[:RECENT_SESSIONS_LIMIT]:
        stages = sorted(
            (stage for stage in view.stages if stage.batch_id == batch.batch_id),
            key=lambda stage: stage.at,
        )
        sessions.append(
            RecentSession(
                batch_id=batch.batch_id,
                ticket=batch.ticket,
                state=batch.state,
                branch=batch.branch,
                created_at=batch.created_at,
                route=tuple(RouteStep(stage.role, stage.state) for stage in stages),
                updated_at=stages[-1].at if stages else batch.created_at,
            )
        )
    return tuple(sessions)


def collect_context(repo: Path) -> HomeContext:
    """Read the Repo Map cached for the project's HEAD (else the latest cached map of another
    commit, shown as stale), the memory status, the project, harness
    and store facts and the recent ledger sessions; builds and writes nothing."""
    head = head_commit(repo)
    try:
        sessions = recent_sessions(load_ledger_view(repo))
    except Exception:  # an unreadable ledger shows no sessions, never stale ones
        sessions = ()
    repo_map = cached_map(repo, head) if head else None
    return HomeContext(
        repo_map=repo_map,
        stale_map=latest_cached_map(repo, exclude=head) if head and repo_map is None else None,
        memory=memory_status(repo),
        project=project_facts(repo),
        harness=harness_install(repo),
        store=store_facts(repo),
        recent_sessions=sessions,
    )


class _CollectDashboard(Protocol):
    def __call__(self, repo: Path, /) -> DashboardData: ...


class _CollectOnlineDashboard(Protocol):
    def __call__(self, repo: Path, /, *, online: bool) -> DashboardData: ...


def collect_home(
    repo: Path,
    *,
    online: bool = False,
    dashboard: _CollectDashboard | _CollectOnlineDashboard = collect_dashboard,
    context: Callable[[Path], HomeContext] = collect_context,
) -> HomeSnapshot:
    """Run the offline checks (with `online`, the online ones too) and read the context cards;
    blocks until both are done. `dashboard` gets `online=True` only for an online collect."""
    # An offline seam takes the repository only; the online flag goes to an online collect alone.
    data = (
        cast(_CollectOnlineDashboard, dashboard)(repo, online=True)
        if online
        else cast(_CollectDashboard, dashboard)(repo)
    )
    return build_home_snapshot(data, context(repo))
