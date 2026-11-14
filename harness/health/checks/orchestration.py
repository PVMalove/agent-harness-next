"""Read-only `orchestration` health-check group (#343-#347).

Reports the lifecycle ledger's own state, blocked batches, dispatches that stopped sending a
heartbeat, worktree directories orphaned from both `git worktree list` and every open batch, and
the disposable data volume `harness cleanup` would remove -- all without importing
`harness.orchestration.*` or `harness.cleanup` at module level.

Like `files.check_orchestration_config`, every check below first reads `context.lock` and returns
`skipped` when the `backend-orchestration` capability is absent, before ever importing an
orchestration module; only then does the import happen, local to the function body. This keeps a
shipped, standalone `harness/health/` (see tests/health/test_health_standalone_package.py, which copies
only `health` and `repo_map`) working with no `harness/orchestration/` and no `harness/cleanup.py`
on disk -- the capability manifest installs both together with `backend-orchestration`, so the
deferred import only ever fires once they are actually present.

Every check only reads state: ledger records, `git worktree list --porcelain`, and a dry-run
`plan_cleanup` preview. None of them call `ledger migrate`, `ledger reset`, `apply_cleanup`, or
`git worktree remove`/`prune` -- nothing here mutates the ledger, worktrees, or disposable data.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

from harness.configuration import read_config_json
from harness.errors import INTERNAL_INVARIANT_REMEDY, HarnessError

from ..context import HealthContext
from ..model import CheckResult, Fix, JsonObject

_MIGRATION_MESSAGE = "леджер оркестрации требует миграции схемы"


def _migration_fix(context: HealthContext) -> Fix:
    return Fix(
        text="выполните миграцию схемы леджера",
        command=context.coordinator_command("ledger", "migrate"),
    )


def _skipped(check_id: str, context: HealthContext) -> CheckResult:
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="skipped",
        message=context.no_orchestration_message(),
    )


class _LedgerState:
    """One read of the lifecycle ledger, shared by the ledger-backed checks in this module so
    none of them repeats the same pointer/generation resolution and error handling.

    Materializes records inside the coordinator's read-only state view, so the same checks work
    with a file ledger and with the runtime store. Nothing reads a virtual store path after the
    view closes, and an unavailable runtime never falls back to the old generation."""

    def __init__(self, repo: Path) -> None:
        from harness.orchestration.core.constants import STATE_REL
        from harness.orchestration.core import state_view
        from harness.orchestration.ledger.ledger_ops import read_state
        from harness.orchestration.ledger.lifecycle import (
            LedgerError,
            LifecycleLedger,
            store_is_authority,
        )

        self.ledger = LifecycleLedger(repo / STATE_REL)
        self.error: str | None = None
        # The runtime error code behind `error`, so a check can tell an unavailable runtime.
        self.error_code: str | None = None
        self.status: JsonObject = {}
        self.batches: list[JsonObject] = []
        self.dispatch_statuses: dict[str, JsonObject] = {}
        self.records_root: Path | None = None
        try:
            # File health stays lock-free and never initializes an empty state directory.
            reader = (
                read_state(self.ledger, repo)
                if store_is_authority(self.ledger.root)
                else nullcontext()
            )
            with reader:
                self.status = self.ledger.status()
                if self.needs_migration:
                    return
                if (
                    self.status.get("generation") is None
                    and self.status.get("authority") != "runtime-store"
                ):
                    return
                root = self.ledger.records_root()
                self.records_root = root
                for path in state_view.glob(root / "batches", "*.json"):
                    record = LifecycleLedger.read_record_lenient(path)
                    if record is not None:
                        self.batches.append(record)
                for path in state_view.glob(root / "dispatch-status", "*.json"):
                    record = LifecycleLedger.read_record_lenient(path)
                    if record is not None:
                        self.dispatch_statuses[path.stem] = record
        except (LedgerError, HarnessError) as exc:
            self.error = str(exc)
            code = getattr(exc, "code", None)
            self.error_code = code if isinstance(code, str) else None

    @property
    def unreadable(self) -> bool:
        return self.error is not None

    @property
    def needs_migration(self) -> bool:
        return bool(self.status.get("legacy")) or bool(self.status.get("stale_schema"))


# The same bound as the console's runtime probe (home_facts.RUNTIME_TIMEOUT_SECONDS); kept here
# because the standalone health package imports no console module.
_RUNTIME_TIMEOUT_SECONDS = 2.0


def _serve_fix(context: HealthContext) -> Fix:
    from harness.orchestration.runtime_client import serve_command

    return Fix(
        text="запустите runtime вне песочницы агента и держите его запущенным",
        command=serve_command(context.repo),
    )


def _store_is_authority(repo: Path) -> bool:
    from harness.orchestration.core.constants import STATE_REL
    from harness.orchestration.ledger.lifecycle import store_is_authority

    return store_is_authority(repo / STATE_REL)


def check_runtime(context: HealthContext) -> CheckResult:
    """Whether the runtime of a runtime-store repository answers one `status` request; it is
    never started here. A file ledger needs no runtime, so the check is skipped."""
    check_id = "orchestration.runtime"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    if not _store_is_authority(context.repo):
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="skipped",
            message="леджер файловый: runtime не нужен",
        )
    from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError

    try:
        client = RuntimeClient(context.repo)
        reply = client.call(
            "status",
            operation_id=f"health-status-{client.paths.repo_id}",
            timeout_seconds=_RUNTIME_TIMEOUT_SECONDS,
        )
    except RuntimeClientError as error:
        if error.code == "runtime_unavailable":
            return CheckResult(
                id=check_id,
                group="orchestration",
                status="fail",
                message=f"runtime не отвечает: {error}",
                fix=_serve_fix(context),
            )
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"runtime отказал ({error.code}): {error}",
            fix=Fix(text=error.remedy),
        )
    protocol = reply.hello.get("protocol")
    version = (
        f"{protocol.get('major')}.{protocol.get('minor')}"
        if isinstance(protocol, dict)
        else "?"
    )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message=(
            f"runtime работает: pid={reply.result.get('pid', '?')} "
            f"server_version={reply.hello.get('server_version', '?')} протокол={version}"
        ),
    )


def check_ledger_summary(context: HealthContext) -> CheckResult:
    check_id = "orchestration.ledger_summary"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    state = _LedgerState(context.repo)
    if state.unreadable:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"леджер оркестрации недоступен: {state.error}",
            fix=_serve_fix(context) if state.error_code == "runtime_unavailable" else None,
        )
    if state.needs_migration:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message=_MIGRATION_MESSAGE,
            fix=_migration_fix(context),
        )
    if state.records_root is None:
        from harness.orchestration.runtime_client import init_command

        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message="у проекта ещё нет runtime store оркестрации",
            fix=Fix(
                text="создайте runtime store: команду выполняет человек со своим approval",
                command=init_command(context.repo),
            ),
        )
    counts: dict[str, int] = {}
    for batch in state.batches:
        batch_state = batch.get("state")
        if isinstance(batch_state, str):
            counts[batch_state] = counts.get(batch_state, 0) + 1
    # failed/abandoned batches are informational only: they are counted here but never change
    # this check's status away from "ok".
    counts_text = (
        ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        if counts
        else "батчей нет"
    )
    location = (
        "authority=runtime-store"
        if state.status.get("authority") == "runtime-store"
        else f"generation={state.status['generation']}"
    )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message=(
            f"леджер: {location} "
            f"schema_version={state.status['version']}; батчи по состояниям: {counts_text}"
        ),
    )


def _age(created_at: object) -> str:
    """Human age of an ISO timestamp, or "?" when it is missing or unparsable."""
    from datetime import UTC, datetime

    if not isinstance(created_at, str):
        return "?"
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return "?"
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    seconds = max(0, int((datetime.now(UTC) - created).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60}м"
    if seconds < 86400:
        return f"{seconds // 3600}ч"
    return f"{seconds // 86400}д"


def check_unfinished_batches(context: HealthContext) -> CheckResult:
    """Informational: every batch still in flight with its ticket, branch, worktree and age. Blocked
    batches are warned about by check_blocked_batches, stalled dispatches by check_stale_dispatches."""
    check_id = "orchestration.unfinished_batches"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    state = _LedgerState(context.repo)
    if state.unreadable:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"леджер оркестрации недоступен: {state.error}",
        )
    if state.needs_migration:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message=_MIGRATION_MESSAGE,
            fix=_migration_fix(context),
        )
    from harness.orchestration.ledger.recovery_chain import terminal

    unfinished = [batch for batch in state.batches if not terminal(batch)]
    if not unfinished:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="ok",
            message="незавершённых батчей нет",
        )
    described = [
        f"{batch.get('batch_id', '?')} [{batch.get('state', '?')}] "
        f"ticket={batch.get('ticket') or '?'} branch={batch.get('branch') or '?'} "
        f"worktree={batch.get('worktree') or '?'} возраст={_age(batch.get('created_at'))}"
        for batch in sorted(
            unfinished, key=lambda batch: str(batch.get("created_at", ""))
        )
    ]
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message=f"незавершённые батчи ({len(unfinished)}): " + "; ".join(described),
    )


def _attention_policy_threshold(repo: Path) -> int:
    """Resolve `attention_policy.stale_dispatch_seconds` the same way the coordinator does:
    a positive integer override in `.harness/orchestration.json`, else the built-in default."""

    from harness.orchestration.core.constants import DEFAULT_ATTENTION_POLICY

    config_path = repo / ".harness" / "orchestration.json"
    try:
        config = read_config_json(config_path)
    except (OSError, ValueError):
        config = None
    attention = config.get("attention_policy") if isinstance(config, dict) else None
    if isinstance(attention, dict):
        value = attention.get("stale_dispatch_seconds")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            return value
    threshold = DEFAULT_ATTENTION_POLICY["stale_dispatch_seconds"]
    if not isinstance(threshold, int):
        raise HarnessError(
            "built-in attention_policy.stale_dispatch_seconds is not an integer",
            remedy=INTERNAL_INVARIANT_REMEDY,
        )
    return threshold


def check_blocked_batches(context: HealthContext) -> CheckResult:
    check_id = "orchestration.blocked_batches"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    state = _LedgerState(context.repo)
    if state.unreadable:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"леджер оркестрации недоступен: {state.error}",
        )
    if state.needs_migration:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message=_MIGRATION_MESSAGE,
            fix=_migration_fix(context),
        )
    blocked = sorted(
        batch_id
        for batch in state.batches
        if batch.get("state") == "blocked"
        and isinstance(batch_id := batch.get("batch_id"), str)
    )
    if blocked:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message="заблокированные батчи: " + ", ".join(blocked),
            fix=Fix(
                text="разрешите блокировку через coordinator.py batch decide (в harness console: "
                "Orchestration → «Решение по batch»)"
            ),
        )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message="заблокированных батчей нет",
    )


def check_stale_dispatches(context: HealthContext) -> CheckResult:
    check_id = "orchestration.stale_dispatches"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    state = _LedgerState(context.repo)
    if state.unreadable:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"леджер оркестрации недоступен: {state.error}",
        )
    if state.needs_migration:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message=_MIGRATION_MESSAGE,
            fix=_migration_fix(context),
        )
    if state.records_root is None:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="ok",
            message="леджер оркестрации ещё не инициализирован (диспатчей нет)",
        )
    from harness.orchestration.core.constants import LIVE_DISPATCH_STATES
    from harness.orchestration.core.utils import CoordinatorError, _silent_seconds
    from harness.orchestration.ledger.recovery_chain import terminal

    threshold = _attention_policy_threshold(context.repo)
    stale: list[str] = []
    for batch in state.batches:
        if terminal(batch):
            continue
        entries = batch.get("dispatches")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            dispatch_id = entry.get("dispatch_id")
            if not isinstance(dispatch_id, str):
                continue
            status = state.dispatch_statuses.get(dispatch_id)
            if status is None or status.get("state") not in LIVE_DISPATCH_STATES:
                continue
            try:
                silent = _silent_seconds(status)
            except CoordinatorError:
                continue
            if silent >= threshold:
                stale.append(f"{dispatch_id} ({silent}s)")
    if stale:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message="диспатчи без heartbeat дольше порога: " + ", ".join(sorted(stale)),
            fix=Fix(
                text=(
                    f"порог {threshold}s из attention_policy.stale_dispatch_seconds; "
                    "проверьте застрявшего воркера"
                )
            ),
        )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message="все активные диспатчи посылают heartbeat вовремя",
    )


def _owner(path: Path) -> str:
    try:
        uid = path.stat().st_uid
    except OSError:
        return "неизвестен (доступ отсутствует)"
    if sys.platform == "win32":
        return str(uid)
    import pwd

    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def check_orphaned_worktrees(context: HealthContext) -> CheckResult:
    check_id = "orchestration.orphaned_worktrees"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    from harness.cleanup import _active_worktrees, _registered_worktrees
    from harness.storage import sandboxes_root, storage_root

    repo = context.repo
    registered = _registered_worktrees(repo)
    root = storage_root(repo)
    active = _active_worktrees(root)
    if registered is None or active is None:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="skipped",
            message="не удалось определить осиротевшие воркдеревья (git или леджер недоступны)",
        )
    known = set(registered) | active
    worktree_dirs = [sandboxes_root(repo) / "worktrees", root / "worktrees"]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for worktrees in worktree_dirs:
        if not worktrees.is_dir() or worktrees.is_symlink():
            continue
        for entry in sorted(worktrees.iterdir()):
            if not entry.is_dir() or entry.is_symlink():
                continue
            resolved = entry.resolve()
            if resolved in known or resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(entry)
    if not candidates:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="ok",
            message="осиротевших воркдеревьев нет",
        )
    described = [f"{path} (owner={_owner(path)})" for path in candidates]
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="warn",
        message="осиротевшие каталоги воркдеревьев: " + "; ".join(described),
        fix=Fix(
            text="ничего не удалено; сначала git worktree prune, затем предпросмотр harness cleanup",
            command=context.harness_command("cleanup", str(repo), "--mode", "hard"),
        ),
    )


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB"):
        if value < 1024:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def check_disposable_data(context: HealthContext) -> CheckResult:
    check_id = "orchestration.disposable_data"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    from harness.cleanup import plan_cleanup

    try:
        plan = plan_cleanup(context.repo, mode="hard")
    except ValueError as exc:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"не удалось построить план очистки: {exc}",
        )
    total = 0
    for item in plan["remove"]:
        path = Path(item["path"])
        try:
            if item["kind"] == "file":
                total += path.stat().st_size
            else:
                for sub in path.rglob("*"):
                    try:
                        if sub.is_file():
                            total += sub.stat().st_size
                    except OSError:
                        continue
        except OSError:
            continue
    if total == 0:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="ok",
            message="одноразовых данных для очистки нет",
        )
    # Informational only (epic #341 severity rules): a Repo Map cache or parser bundle is normal,
    # not a risk, so a non-empty plan is neither a warning nor a "Как исправить" remedy - the
    # cleanup hint is part of the message.
    preview = context.harness_command("cleanup", str(context.repo), "--mode", "hard")
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message=(
            f"одноразовых данных на {_human_size(total)} (информация, ничего не удалено); "
            f"предпросмотр очистки: {preview}"
        ),
    )


_ADAPTERS = (".harness/adapters/claude_worker.py", ".harness/adapters/codex_worker.py")


def check_adapters(context: HealthContext) -> CheckResult:
    """Whether the external adapters on disk are the ones the installed harness version shipped:
    the sha256 of each must equal its hash in `.harness/harness.lock`."""
    check_id = "orchestration.adapters"
    if not context.orchestration_enabled() or context.lock is None:
        return _skipped(check_id, context)
    version = context.lock.get("package_version", "?")
    hashes = context.lock.get("files")
    problems: list[str] = []
    for relative in _ADAPTERS:
        expected = hashes.get(relative) if isinstance(hashes, dict) else None
        path = context.repo / relative
        if not isinstance(expected, str) or not path.is_file():
            problems.append(f"адаптер {relative} не установлен")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(f"адаптер {relative} не совпадает с версией harness {version}")
    if problems:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message="; ".join(problems),
            fix=Fix(
                text="переустановите адаптеры текущей версии harness",
                command=context.harness_command("update", str(context.repo)),
            ),
        )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message=f"адаптеры claude и codex совпадают с версией harness {version}",
    )


_WORKER_BINARIES = ("claude", "codex")


_IMAGE_TIMEOUT_SECONDS = 10


def _external_needs(repo: Path) -> tuple[set[str], dict[str, set[str]]]:
    """What the external roles run by default: the worker binaries of the host roles (the
    `default_runtime` of a role, else every runtime it names), and the images by engine of the
    roles the container executor runs (#1125). A container role needs no host binary."""
    from harness.orchestration.contract import role_access_authored

    try:
        config = read_config_json(repo / ".harness" / "orchestration.json")
    except (OSError, ValueError):
        config = None
    if not isinstance(config, dict):
        return set(), {}
    plans = config.get("assignment_plans")
    extensions = config.get("extensions")
    policy = config.get("access_policy")
    docker = isinstance(extensions, dict) and extensions.get("runtime_access") == "docker"
    binaries: set[str] = set()
    images: dict[str, set[str]] = {}
    for role, plan in plans.items() if isinstance(plans, dict) else ():
        if not isinstance(plan, dict) or plan.get("transport") != "external":
            continue
        if docker and role_access_authored(policy, role):
            container = _role_container(policy, role)
            engine = container.get("engine", "docker")
            tags = images.setdefault(str(engine), set())
            tags.update(
                str(container[key])
                for key in ("worker_image", "proxy_image")
                if isinstance(container.get(key), str)
            )
            continue
        runtimes = plan.get("runtimes")
        default = plan.get("default_runtime")
        names = (
            [default]
            if isinstance(default, str)
            else list(runtimes)
            if isinstance(runtimes, dict)
            else []
        )
        binaries.update(name for name in names if name in _WORKER_BINARIES)
    return binaries, images


def _role_container(policy: object, role: str) -> dict[str, object]:
    """The `container` component of ``role``: its own override replaces the default whole."""
    if not isinstance(policy, dict):
        return {}
    layers = [policy.get("defaults")]
    roles = policy.get("roles")
    if isinstance(roles, dict):
        layers.append(roles.get(role))
    container: dict[str, object] = {}
    for layer in layers:
        if isinstance(layer, dict) and isinstance(layer.get("container"), dict):
            container = layer["container"]
    return container


def _find_binary(name: str, search_path: str) -> str | None:
    """`name` on the serve PATH; `claude` also in `~/.local/bin`, as its adapter looks (#1123)."""
    found = shutil.which(name, path=search_path)
    if found is None and name == "claude":
        found = shutil.which(name, path=str(Path.home() / ".local" / "bin"))
    return found


def _image_present(engine: str, tag: str) -> bool:
    """Whether the local image store of ``engine`` holds ``tag``; the check pulls nothing."""
    try:
        result = subprocess.run(
            [engine, "image", "inspect", "--format", "{{.Id}}", tag],
            capture_output=True,
            text=True,
            check=False,
            timeout=_IMAGE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def check_worker_binaries(context: HealthContext) -> CheckResult:
    """Whether `claude` and `codex` resolve on the PATH of the `harness-runtime serve` environment,
    where the supervised adapters look them up. A binary an external role needs is a failure.

    A role the container executor runs needs the engine on that PATH and its images in the
    engine's local store instead: the agent CLI lives in the worker image (#1125)."""
    check_id = "orchestration.worker_binaries"
    if not context.orchestration_enabled():
        return _skipped(check_id, context)
    if not _store_is_authority(context.repo):
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="skipped",
            message="леджер файловый: worker запускает адаптер в окружении координатора",
        )
    from harness.orchestration.runtime_client import RuntimeClient, RuntimeClientError

    try:
        client = RuntimeClient(context.repo)
        reply = client.call(
            "status",
            operation_id=f"health-search-path-{client.paths.repo_id}",
            timeout_seconds=_RUNTIME_TIMEOUT_SECONDS,
        )
    except RuntimeClientError as error:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="skipped",
            message=f"runtime недоступен ({error.code}): см. orchestration.runtime",
        )
    search_path = reply.result.get("search_path")
    if not isinstance(search_path, str):
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="warn",
            message="runtime не сообщает PATH: обновите и перезапустите serve",
            fix=_serve_fix(context),
        )
    missing = [name for name in _WORKER_BINARIES if _find_binary(name, search_path) is None]
    binaries, images = _external_needs(context.repo)
    required = sorted(binaries.intersection(missing))
    container_problems: list[str] = []
    for engine, tags in sorted(images.items()):
        engine_path = _find_binary(engine, search_path)
        if engine_path is None:
            container_problems.append(f"в PATH окружения serve нет движка {engine}")
            continue
        container_problems.extend(
            f"в {engine} нет образа {tag}"
            for tag in sorted(tags)
            if not _image_present(engine_path, tag)
        )
    if container_problems:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message="роли в контейнере не запустятся: " + "; ".join(container_problems),
            fix=Fix(
                text="установите движок в PATH окружения serve и соберите образы по "
                ".harness/docs/container-executor.md; харнесс образы не собирает и не скачивает",
                command=_serve_fix(context).command,
            ),
        )
    if required:
        return CheckResult(
            id=check_id,
            group="orchestration",
            status="fail",
            message=f"в PATH окружения serve нет {', '.join(required)} для ролей с "
            "транспортом external",
            fix=Fix(
                text=f"установите {', '.join(required)} в PATH окружения serve и "
                "перезапустите runtime",
                command=_serve_fix(context).command,
            ),
        )
    return CheckResult(
        id=check_id,
        group="orchestration",
        status="ok",
        message="worker-бинарники в PATH окружения serve найдены"
        if not missing
        else f"в PATH окружения serve нет {', '.join(missing)}; роли с транспортом "
        "external их не используют",
    )
