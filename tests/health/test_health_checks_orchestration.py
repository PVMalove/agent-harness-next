"""Group 'orchestration' health checks (#347): read-only reporting on the lifecycle ledger,
worktree directories, and disposable `.sandboxes` data, gated on the `backend-orchestration`
capability exactly like `files.check_orchestration_config` already is."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping

import pytest

from harness.health.checks import orchestration as checks
from harness.health.context import HealthContext, shell_join
from harness.health.model import CheckResult
from harness.orchestration.core.constants import STATE_REL
from harness.orchestration.ledger.lifecycle import (
    STORE_LEDGER_VERSION,
    JsonObject,
    JsonValue,
    _canonical,
)
from harness.orchestration.runtime_client import (
    RuntimeClient,
    RuntimeClientError,
    RuntimeReply,
    serve_command,
)
from tests.orchestration.runtime_store_support import (
    ServingRuntime,
    serve_new_project,
    store_call,
)

_NO_CAPABILITY_LOCK: dict[str, object] = {"capabilities": []}
_ORCHESTRATION_LOCK: dict[str, object] = {"capabilities": ["backend-orchestration"]}

_CHECK_FUNCTIONS: list[Callable[[HealthContext], CheckResult]] = [
    checks.check_ledger_summary,
    checks.check_unfinished_batches,
    checks.check_blocked_batches,
    checks.check_stale_dispatches,
    checks.check_orphaned_worktrees,
    checks.check_disposable_data,
    checks.check_adapters,
    checks.check_worker_binaries,
]


def _context(repo: Path, lock: dict[str, object] | None = None) -> HealthContext:
    return HealthContext(repo=repo, lock=lock, online=False)


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


class StoreLedger:
    """The runtime store of a new project (ADR 0036) and the records a check reads, written
    straight through ``state.write``: the checks summarise batches and dispatches, whatever
    command wrote them."""

    def __init__(self, repo: Path, runtime: ServingRuntime) -> None:
        self.repo = repo
        self.runtime = runtime

    def write(
        self, path: str, record: JsonObject, *, batch_id: str | None = None
    ) -> None:
        mutation: JsonObject = {
            "op": "create",
            "path": path,
            "content": _canonical(record),
        }
        store_call(
            self.repo,
            self.runtime,
            "state.write",
            {"mutations": [mutation]},
            batch_id=batch_id,
        )


@pytest.fixture
def ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[StoreLedger]:
    """``tmp_path`` as a git repository with a served runtime store; health reaches the runtime
    through ``XDG_RUNTIME_DIR``."""
    _init_repo(tmp_path)
    runtime = serve_new_project(tmp_path)
    monkeypatch.setenv("XDG_RUNTIME_DIR", runtime.environ["XDG_RUNTIME_DIR"])
    try:
        yield StoreLedger(tmp_path, runtime)
    finally:
        runtime.stop()


def _write_batch(
    ledger: StoreLedger,
    batch_id: str,
    state: str,
    dispatches: list[JsonObject] | None = None,
    **fields: JsonValue,
) -> None:
    dispatch_entries: list[JsonValue] = list(dispatches or [])
    record: JsonObject = {
        "batch_id": batch_id,
        "state": state,
        "coordinator_approval": None,
        "dispatches": dispatch_entries,
        **fields,
    }
    ledger.write(f"plans/{batch_id}.json", {"batch_id": batch_id}, batch_id=batch_id)
    ledger.write(f"batches/{batch_id}.json", record, batch_id=batch_id)
    # The store keeps a dispatch record for every dispatch a batch names: a status record of
    # the dispatch refers to it.
    for entry in dispatches or []:
        ledger.write(
            f"dispatches/{entry['dispatch_id']}.json",
            {**entry, "batch_id": batch_id},
            batch_id=batch_id,
        )


def _write_dispatch_status(
    ledger: StoreLedger, dispatch_id: str, status: JsonObject
) -> None:
    ledger.write(f"dispatch-status/{dispatch_id}.json", status)


# --- capability gating (DoD 1) ----------------------------------------------------------------


@pytest.mark.parametrize("check_fn", _CHECK_FUNCTIONS)
def test_skips_without_backend_orchestration_capability(
    tmp_path: Path, check_fn: Callable[[HealthContext], CheckResult]
) -> None:
    result = check_fn(_context(tmp_path, lock=_NO_CAPABILITY_LOCK))

    assert result.status == "skipped"
    assert result.group == "orchestration"


@pytest.mark.parametrize("check_fn", _CHECK_FUNCTIONS)
def test_skips_without_a_lock_at_all(
    tmp_path: Path, check_fn: Callable[[HealthContext], CheckResult]
) -> None:
    result = check_fn(_context(tmp_path, lock=None))

    assert result.status == "skipped"


# --- orchestration.ledger_summary (DoD 2, 3) --------------------------------------------------


def test_ledger_summary_leads_a_project_without_state_to_runtime_init(
    tmp_path: Path,
) -> None:
    result = checks.check_ledger_summary(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "warn"
    assert result.fix is not None
    assert result.fix.command is not None
    assert result.fix.command.startswith(
        f"harness-runtime init --repo {tmp_path.resolve()} --approved-by"
    )
    assert not (tmp_path / STATE_REL).exists()


def test_ledger_summary_fails_on_an_unreadable_ledger_pointer(tmp_path: Path) -> None:
    pointer = tmp_path / ".harness" / "orchestration" / "state" / "ledger.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("not json", encoding="utf-8")

    result = checks.check_ledger_summary(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "fail"
    assert "недоступен" in result.message


def test_ledger_summary_warns_on_legacy_state_requiring_migration(
    tmp_path: Path,
) -> None:
    legacy_batches = tmp_path / ".harness" / "orchestration" / "state" / "batches"
    legacy_batches.mkdir(parents=True)
    (legacy_batches / "batch-legacy.json").write_text(
        json.dumps(
            {"batch_id": "batch-legacy", "state": "completed", "dispatches": []}
        ),
        encoding="utf-8",
    )

    result = checks.check_ledger_summary(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "warn"
    assert result.fix is not None
    # Runnable as printed from any directory: interpreter and coordinator path are absolute.
    assert result.fix.command == shell_join(
        [
            sys.executable,
            str(tmp_path / ".harness" / "orchestration" / "coordinator.py"),
            "--repo",
            str(tmp_path),
            "ledger",
            "migrate",
        ]
    )


def test_ledger_summary_warns_on_a_stale_schema_version(tmp_path: Path) -> None:
    state_root = tmp_path / ".harness" / "orchestration" / "state"
    state_root.mkdir(parents=True)
    (state_root / "ledger.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generation": "generation-old",
                "selected_at": "2020-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = checks.check_ledger_summary(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "warn"
    assert result.fix is not None
    # Runnable as printed from any directory: interpreter and coordinator path are absolute.
    assert result.fix.command == shell_join(
        [
            sys.executable,
            str(tmp_path / ".harness" / "orchestration" / "coordinator.py"),
            "--repo",
            str(tmp_path),
            "ledger",
            "migrate",
        ]
    )


def test_ledger_summary_reports_generation_schema_and_batch_counts(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    _write_batch(ledger, "batch-a", "completed")
    _write_batch(ledger, "batch-b", "abandoned")
    _write_batch(ledger, "batch-c", "active")

    result = checks.check_ledger_summary(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    # failed/abandoned batches are informational only: the check still reports "ok".
    assert result.status == "ok"
    assert "completed=1" in result.message
    assert "abandoned=1" in result.message
    assert "active=1" in result.message


def test_unfinished_batches_excludes_legacy_operator_abandonment(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    approval: JsonObject = {
        "approved_by": "Owner",
        "approved_at": "2026-10-01T00:00:00+00:00",
    }
    _write_batch(
        ledger,
        "batch-abandoned",
        "failed",
        abandoned={
            **approval,
            "reason": "The owner stopped this attempt.",
            "abandoned_at": approval["approved_at"],
        },
        coordinator_decisions=[{"decision": "abandon", **approval}],
    )
    _write_batch(ledger, "batch-retryable", "failed")

    result = checks.check_unfinished_batches(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )

    assert result.status == "ok"
    assert "batch-abandoned" not in result.message
    assert "batch-retryable" in result.message


# --- orchestration.blocked_batches (DoD 3) ------------------------------------------------------


def test_blocked_batches_warns_and_names_only_the_blocked_batch(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    _write_batch(ledger, "batch-blocked", "blocked")
    _write_batch(ledger, "batch-active", "active")

    result = checks.check_blocked_batches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "warn"
    assert "batch-blocked" in result.message
    assert "batch-active" not in result.message


def test_blocked_batches_ok_when_none_are_blocked(
    tmp_path: Path, ledger: StoreLedger
) -> None:
    _write_batch(ledger, "batch-active", "active")

    result = checks.check_blocked_batches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "ok"


def test_blocked_batches_fails_on_an_unreadable_ledger(tmp_path: Path) -> None:
    pointer = tmp_path / ".harness" / "orchestration" / "state" / "ledger.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text("not json", encoding="utf-8")

    result = checks.check_blocked_batches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "fail"


# --- orchestration.stale_dispatches (DoD 3, architect risk #3) ---------------------------------


def test_stale_dispatches_warns_past_the_threshold(
    tmp_path: Path, ledger: StoreLedger
) -> None:
    _write_batch(
        ledger,
        "batch-live",
        "active",
        dispatches=[{"dispatch_id": "dispatch-stale", "state": "working"}],
    )
    _write_dispatch_status(
        ledger,
        "dispatch-stale",
        {
            "dispatch_id": "dispatch-stale",
            "state": "working",
            "heartbeat_at": "2020-01-01T00:00:00+00:00",
        },
    )

    result = checks.check_stale_dispatches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "warn"
    assert "dispatch-stale" in result.message


def test_stale_dispatches_ok_when_heartbeat_is_recent(
    tmp_path: Path, ledger: StoreLedger
) -> None:
    recent = datetime.now(UTC).isoformat()
    _write_batch(
        ledger,
        "batch-live",
        "active",
        dispatches=[{"dispatch_id": "dispatch-fresh", "state": "working"}],
    )
    _write_dispatch_status(
        ledger,
        "dispatch-fresh",
        {"dispatch_id": "dispatch-fresh", "state": "working", "heartbeat_at": recent},
    )

    result = checks.check_stale_dispatches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "ok"


def test_stale_dispatches_ignores_dispatches_of_terminal_batches(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    _write_batch(
        ledger,
        "batch-done",
        "completed",
        dispatches=[{"dispatch_id": "dispatch-old", "state": "reported"}],
    )
    _write_dispatch_status(
        ledger,
        "dispatch-old",
        {
            "dispatch_id": "dispatch-old",
            # Even a "working" status record on a terminal batch must not be flagged: the batch
            # itself, not the dispatch's own last recorded state, decides whether it is in scope.
            "state": "working",
            "heartbeat_at": "2020-01-01T00:00:00+00:00",
        },
    )

    result = checks.check_stale_dispatches(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "ok"


def test_stale_dispatches_uses_the_project_configured_threshold_over_the_default(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    """Architect risk #3: the threshold must actually come from
    .harness/orchestration.json when set, not silently fall back to the built-in default."""
    ten_minutes_ago = (datetime.now(UTC) - timedelta(seconds=600)).isoformat()
    _write_batch(
        ledger,
        "batch-live",
        "active",
        dispatches=[{"dispatch_id": "dispatch-recent", "state": "working"}],
    )
    _write_dispatch_status(
        ledger,
        "dispatch-recent",
        {
            "dispatch_id": "dispatch-recent",
            "state": "working",
            "heartbeat_at": ten_minutes_ago,
        },
    )

    # The built-in default (3600s) tolerates a 600s-old heartbeat.
    default_result = checks.check_stale_dispatches(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )
    assert default_result.status == "ok"

    # A project override lowers the threshold below 600s, so the same heartbeat now warns.
    config_path = tmp_path / ".harness" / "orchestration.json"
    config_path.write_text(
        json.dumps({"attention_policy": {"stale_dispatch_seconds": 60}}),
        encoding="utf-8",
    )

    overridden_result = checks.check_stale_dispatches(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )
    assert overridden_result.status == "warn"


# --- orchestration.orphaned_worktrees (DoD 4) --------------------------------------------------


def test_owner_reports_access_missing_on_a_stat_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(_self: Path) -> int:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "stat", _raise)

    assert checks._owner(tmp_path) == "неизвестен (доступ отсутствует)"


def test_owner_falls_back_to_uid_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "win32")

    assert checks._owner(tmp_path) == str(tmp_path.stat().st_uid)


def test_orphaned_worktrees_warns_with_owner_and_deletes_nothing(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    worktrees_dir = tmp_path / ".harness" / ".sandboxes" / "worktrees"
    orphan = worktrees_dir / "orphan-1"
    orphan.mkdir(parents=True)
    marker = orphan / "marker.txt"
    marker.write_text("keep me", encoding="utf-8")

    result = checks.check_orphaned_worktrees(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )

    assert result.status == "warn"
    assert "orphan-1" in result.message
    assert "owner=" in result.message
    assert result.fix is not None
    assert result.fix.command == shell_join(
        ["harness", "cleanup", str(tmp_path), "--mode", "hard"]
    )
    assert orphan.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep me"


def test_orphaned_worktrees_ok_when_registered_by_git_worktree_list(
    tmp_path: Path,
) -> None:
    _init_repo(tmp_path)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        cwd=tmp_path,
        check=True,
    )
    worktree_path = tmp_path / ".harness" / ".sandboxes" / "worktrees" / "linked"
    worktree_path.parent.mkdir(parents=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", "feature/issue-1-x", str(worktree_path)],
        cwd=tmp_path,
        check=True,
    )

    result = checks.check_orphaned_worktrees(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )

    assert result.status == "ok"
    assert worktree_path.is_dir()  # still present; nothing was pruned


def test_orphaned_worktrees_ok_when_referenced_by_an_active_batch(
    tmp_path: Path,
    ledger: StoreLedger,
) -> None:
    worktree_path = tmp_path / ".harness" / ".sandboxes" / "worktrees" / "active-1"
    worktree_path.mkdir(parents=True)
    _write_batch(ledger, "batch-active", "active", worktree=str(worktree_path))

    result = checks.check_orphaned_worktrees(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )

    assert result.status == "ok"


def test_orphaned_worktrees_skipped_when_git_worktree_list_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Story 21: "not checked" is never reported as "passed" - a failed `git worktree list`
    means skipped."""
    import harness.cleanup

    monkeypatch.setattr(harness.cleanup, "_registered_worktrees", lambda repo: None)

    result = checks.check_orphaned_worktrees(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )

    assert result.status == "skipped"


# --- orchestration.disposable_data (DoD 5) ------------------------------------------------------


def test_disposable_data_ok_when_nothing_to_clean(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    result = checks.check_disposable_data(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "ok"


def test_disposable_data_reports_a_nonzero_size_as_information_with_a_cleanup_hint(
    tmp_path: Path,
) -> None:
    """Epic #341 severity rules: disposable data is informational - never a `warn`."""
    _init_repo(tmp_path)
    scratch = tmp_path / ".harness" / ".sandboxes" / "scratch"
    scratch.mkdir(parents=True)
    stale_file = scratch / "old.txt"
    stale_file.write_text("x" * 100, encoding="utf-8")
    old_time = time.time() - 48 * 3600
    os.utime(stale_file, (old_time, old_time))

    result = checks.check_disposable_data(_context(tmp_path, lock=_ORCHESTRATION_LOCK))

    assert result.status == "ok"
    assert "100 B" in result.message
    # An informational `ok` carries no "Как исправить" remedy; the preview hint is in the message.
    assert result.fix is None
    assert (
        shell_join(["harness", "cleanup", str(tmp_path), "--mode", "hard"])
        in result.message
    )
    assert stale_file.exists()  # preview only; nothing was removed


# --- orchestration.adapters (#1124) -------------------------------------------------------------

_ADAPTERS = (".harness/adapters/claude_worker.py", ".harness/adapters/codex_worker.py")


def _install_adapters(repo: Path) -> dict[str, object]:
    """Both adapters on disk and the lock of harness 9.9.9 that installed them."""
    files: dict[str, object] = {}
    for relative in _ADAPTERS:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"# {relative}\n".encode())
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {**_ORCHESTRATION_LOCK, "package_version": "9.9.9", "files": files}


def test_adapters_ok_when_both_match_the_installed_harness_version(
    tmp_path: Path,
) -> None:
    lock = _install_adapters(tmp_path)

    result = checks.check_adapters(_context(tmp_path, lock=lock))

    assert (result.id, result.group, result.status) == (
        "orchestration.adapters",
        "orchestration",
        "ok",
    )
    assert "9.9.9" in result.message


def test_adapters_fail_when_one_is_missing_from_the_lock_or_the_disk(
    tmp_path: Path,
) -> None:
    lock = _install_adapters(tmp_path)
    files = lock["files"]
    assert isinstance(files, dict)
    del files[".harness/adapters/codex_worker.py"]
    (tmp_path / ".harness/adapters/claude_worker.py").unlink()

    result = checks.check_adapters(_context(tmp_path, lock=lock))

    assert result.status == "fail"
    assert "claude_worker.py" in result.message
    assert "codex_worker.py" in result.message
    assert "не установлен" in result.message
    assert result.fix is not None
    assert result.fix.command == shell_join(["harness", "update", str(tmp_path)])


def test_adapters_fail_when_one_differs_from_the_installed_harness_version(
    tmp_path: Path,
) -> None:
    lock = _install_adapters(tmp_path)
    (tmp_path / ".harness/adapters/codex_worker.py").write_text("# old\n")

    result = checks.check_adapters(_context(tmp_path, lock=lock))

    assert result.status == "fail"
    assert "codex_worker.py" in result.message
    assert "claude_worker.py" not in result.message
    assert "9.9.9" in result.message


# --- orchestration.worker_binaries (#1124) ------------------------------------------------------


def _store_repo(repo: Path, plans: dict[str, object]) -> HealthContext:
    _init_repo(repo)
    state = repo / ".harness" / "orchestration" / "state"
    state.mkdir(parents=True)
    (state / "ledger.json").write_text(
        json.dumps({"version": STORE_LEDGER_VERSION}), encoding="utf-8"
    )
    (repo / ".harness" / "orchestration.json").write_text(
        json.dumps({"assignment_plans": plans}), encoding="utf-8"
    )
    return _context(repo, lock=_ORCHESTRATION_LOCK)


def _status(result: JsonObject) -> Callable[[RuntimeClient, str], RuntimeReply]:
    def answer(self: RuntimeClient, operation: str, **kwargs: object) -> RuntimeReply:
        assert operation == "status"
        return RuntimeReply(hello={}, result=result, revision=None)

    return answer


def _binary(directory: Path, name: str) -> None:
    """An executable ``name`` that ``shutil.which`` finds on POSIX and on Windows."""
    directory.mkdir(parents=True, exist_ok=True)
    for file_name in (name, f"{name}.cmd"):
        path = directory / file_name
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)


_RUNTIME = {"profiles": ["p"], "model": "m", "effort": "high"}


def test_worker_binaries_fail_for_an_external_role_whose_binary_serve_cannot_find(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _store_repo(
        tmp_path,
        {
            "developer": {"transport": "external", "runtimes": {"codex": _RUNTIME}},
            "architect": {"runtimes": {"claude": _RUNTIME}},
        },
    )
    bin_dir = tmp_path / "serve-bin"
    _binary(bin_dir, "claude")
    monkeypatch.setattr(RuntimeClient, "call", _status({"search_path": str(bin_dir)}))

    result = checks.check_worker_binaries(context)

    assert (result.id, result.group, result.status) == (
        "orchestration.worker_binaries",
        "orchestration",
        "fail",
    )
    assert "codex" in result.message
    assert result.fix is not None
    assert "установите codex в PATH окружения serve" in result.fix.text
    assert result.fix.command == serve_command(tmp_path)


def test_worker_binaries_ok_lists_a_missing_binary_no_external_role_needs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _store_repo(
        tmp_path,
        {
            "developer": {
                "transport": "external",
                "runtimes": {"claude": _RUNTIME, "codex": _RUNTIME},
                "default_runtime": "claude",
            },
        },
    )
    bin_dir = tmp_path / "serve-bin"
    _binary(bin_dir, "claude")
    monkeypatch.setattr(RuntimeClient, "call", _status({"search_path": str(bin_dir)}))

    result = checks.check_worker_binaries(context)

    assert result.status == "ok"
    assert "codex" in result.message


def test_worker_binaries_warn_when_the_runtime_reports_no_search_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _store_repo(tmp_path, {})
    monkeypatch.setattr(RuntimeClient, "call", _status({"pid": 1}))

    result = checks.check_worker_binaries(context)

    assert result.status == "warn"
    assert "PATH" in result.message


def test_worker_binaries_skip_on_a_file_ledger_or_an_unavailable_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> RuntimeReply:
        raise RuntimeClientError(
            "runtime_unavailable", "no answer", remedy="start it", domain="infrastructure"
        )

    monkeypatch.setattr(RuntimeClient, "call", refuse)
    store = tmp_path / "store"
    store.mkdir()

    file_ledger = checks.check_worker_binaries(
        _context(tmp_path, lock=_ORCHESTRATION_LOCK)
    )
    unavailable = checks.check_worker_binaries(_store_repo(store, {}))

    assert file_ledger.status == "skipped"
    assert unavailable.status == "skipped"
    assert "orchestration.runtime" in unavailable.message


def _container_repo(repo: Path, roles: Mapping[str, object]) -> HealthContext:
    context = _store_repo(
        repo,
        {
            "developer": {"transport": "external", "runtimes": {"claude": _RUNTIME}},
            "code-review": {"transport": "external", "runtimes": {"claude": _RUNTIME}},
        },
    )
    path = repo / ".harness" / "orchestration.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["extensions"] = {"runtime_access": "docker"}
    config["access_policy"] = {
        "defaults": {"container": {"engine": "podman", "worker_image": "worker:local"}},
        "roles": roles,
    }
    path.write_text(json.dumps(config), encoding="utf-8")
    return context


def test_worker_binaries_need_no_host_agent_for_a_container_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1125: the agent CLI of a container role lives in its image, not on the serve PATH."""
    context = _container_repo(tmp_path, {})
    bin_dir = tmp_path / "serve-bin"
    _binary(bin_dir, "podman")
    monkeypatch.setattr(RuntimeClient, "call", _status({"search_path": str(bin_dir)}))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    seen: list[tuple[str, str]] = []

    def present(engine: str, tag: str) -> bool:
        seen.append((engine, tag))
        return True

    monkeypatch.setattr(checks, "_image_present", present)

    result = checks.check_worker_binaries(context)

    assert result.status == "ok", result.message
    assert seen == [(str(bin_dir / "podman"), "worker:local")]


def test_worker_binaries_fail_for_a_container_role_without_its_engine_or_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roles = {"code-review": {"container": {"engine": "docker", "worker_image": "review:1"}}}
    context = _container_repo(tmp_path, roles)
    bin_dir = tmp_path / "serve-bin"
    _binary(bin_dir, "podman")
    monkeypatch.setattr(RuntimeClient, "call", _status({"search_path": str(bin_dir)}))
    monkeypatch.setattr(checks, "_image_present", lambda engine, tag: False)

    result = checks.check_worker_binaries(context)

    assert result.status == "fail"
    assert "движка docker" in result.message
    assert "в podman нет образа worker:local" in result.message
    assert result.fix is not None


def test_worker_binaries_find_claude_in_user_local_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1123: the adapter falls back to ``~/.local/bin``; the check looks there too."""
    context = _store_repo(
        tmp_path,
        {"developer": {"transport": "external", "runtimes": {"claude": _RUNTIME}}},
    )
    home = tmp_path / "home"
    _binary(home / ".local" / "bin", "claude")
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(
        RuntimeClient, "call", _status({"search_path": str(tmp_path / "empty")})
    )

    result = checks.check_worker_binaries(context)

    assert result.status == "ok", result.message
