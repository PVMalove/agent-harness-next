"""Сквозные тесты CLI harness health для группы проверок orchestration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.health.model import JsonObject
from harness.orchestration.ledger.lifecycle import JsonObject as LedgerJsonObject
from harness.orchestration.ledger.lifecycle import JsonValue as LedgerJsonValue
from tests.health.test_health_checks_orchestration import StoreLedger
from tests.orchestration.runtime_store_support import serve_new_project

_HARNESS_BIN = Path(__file__).resolve().parents[2] / "harness" / "bin" / "harness.py"

_ORCHESTRATION_CHECK_IDS = [
    "orchestration.runtime",
    "orchestration.ledger_summary",
    "orchestration.unfinished_batches",
    "orchestration.blocked_batches",
    "orchestration.stale_dispatches",
    "orchestration.orphaned_worktrees",
    "orchestration.disposable_data",
    "orchestration.adapters",
    "orchestration.worker_binaries",
]


def _init_repo(path: Path) -> None:
    """Инициализировать пустой git-репозиторий по указанному пути."""
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def _write_lock(repo: Path, capabilities: list[str]) -> None:
    """Записать файл harness.lock с заданным списком возможностей."""
    lock_path = repo / ".harness" / "harness.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"capabilities": capabilities}), encoding="utf-8")


def _write_batch(
    ledger: StoreLedger,
    batch_id: str,
    state: str,
    dispatches: list[LedgerJsonObject] | None = None,
    worktree: str = "",
    ticket: str = "",
    branch: str = "",
    created_at: str = "",
) -> None:
    """Записать неизменяемые записи плана и пакета в леджер жизненного цикла."""
    dispatch_entries: list[LedgerJsonValue] = list(dispatches or [])
    record: LedgerJsonObject = {
        "batch_id": batch_id,
        "state": state,
        "coordinator_approval": None,
        "dispatches": dispatch_entries,
        # harness.cleanup._active_worktrees reads batch["worktree"] for every non-terminal
        # batch; a real fixture always has one, so every non-terminal batch below sets it too.
        "worktree": worktree,
        "ticket": ticket,
        "branch": branch,
        "created_at": created_at,
    }
    ledger.write(f"plans/{batch_id}.json", {"batch_id": batch_id}, batch_id=batch_id)
    ledger.write(f"batches/{batch_id}.json", record, batch_id=batch_id)
    for entry in dispatch_entries:
        # The store keeps the dispatch record a status record refers to.
        assert isinstance(entry, dict)
        ledger.write(
            f"dispatches/{entry['dispatch_id']}.json",
            {**entry, "batch_id": batch_id},
            batch_id=batch_id,
        )


def _build_ledger_fixture(ledger: StoreLedger) -> None:
    """Сформировать набор пакетов и диспетчеров для проверки всех состояний оркестрации."""
    _write_batch(ledger, "batch-completed", "completed")
    # The store reader of cleanup refuses a non-terminal batch without a worktree, where the file
    # reader took "" for the repository root.
    _write_batch(
        ledger,
        "batch-blocked",
        "blocked",
        worktree=".harness/.sandboxes/worktrees/issue-100",
    )
    _write_batch(
        ledger,
        "batch-live",
        "active",
        dispatches=[{"dispatch_id": "dispatch-stale", "state": "working"}],
        ticket="#101",
        branch="feature/issue-101-live",
        worktree=".harness/.sandboxes/worktrees/issue-101",
        created_at="2020-01-01T00:00:00+00:00",
    )
    ledger.write(
        "dispatch-status/dispatch-stale.json",
        {
            "dispatch_id": "dispatch-stale",
            "state": "working",
            "heartbeat_at": "2020-01-01T00:00:00+00:00",
        },
    )


def _run_health_json(repo: Path) -> tuple[int, JsonObject]:
    """Выполнить команду harness health --json и вернуть код завершения и разобранный вывод."""
    result = subprocess.run(
        [sys.executable, str(_HARNESS_BIN), "health", str(repo), "--json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return result.returncode, json.loads(result.stdout)


def test_health_json_reports_every_orchestration_check_against_a_ledger_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверить, что CLI health формирует корректный отчет по всем проверкам оркестрации."""
    _init_repo(tmp_path)
    _write_lock(tmp_path, ["backend-orchestration"])
    # The runtime store of a new project (ADR 0036); `harness health` reaches its runtime
    # through XDG_RUNTIME_DIR.
    runtime = serve_new_project(tmp_path)
    monkeypatch.setenv("XDG_RUNTIME_DIR", runtime.environ["XDG_RUNTIME_DIR"])
    try:
        _build_ledger_fixture(StoreLedger(tmp_path, runtime))
        orphan = tmp_path / ".harness" / ".sandboxes" / "worktrees" / "orphan-1"
        orphan.mkdir(parents=True)

        exit_code, data = _run_health_json(tmp_path)
    finally:
        runtime.stop()

    checks_by_id = {check["id"]: check for check in data["checks"]}
    assert checks_by_id["orchestration.ledger_summary"]["status"] == "ok"
    assert "completed=1" in checks_by_id["orchestration.ledger_summary"]["message"]
    unfinished = checks_by_id["orchestration.unfinished_batches"]
    assert unfinished["status"] == "ok"  # informational: ticket, branch, worktree, age
    for detail in (
        "batch-live",
        "#101",
        "feature/issue-101-live",
        "issue-101",
        "возраст=",
    ):
        assert detail in unfinished["message"]
    assert "batch-completed" not in unfinished["message"]
    assert checks_by_id["orchestration.blocked_batches"]["status"] == "warn"
    assert "batch-blocked" in checks_by_id["orchestration.blocked_batches"]["message"]
    assert checks_by_id["orchestration.stale_dispatches"]["status"] == "warn"
    assert "dispatch-stale" in checks_by_id["orchestration.stale_dispatches"]["message"]
    assert checks_by_id["orchestration.orphaned_worktrees"]["status"] == "warn"
    assert "orphan-1" in checks_by_id["orchestration.orphaned_worktrees"]["message"]
    assert checks_by_id["orchestration.disposable_data"]["status"] == "ok"
    # The CLI's own exit-code contract (mirrors test_health_cli.py): 1 only on a 'fail'.
    assert exit_code == (1 if data["summary"]["fail"] else 0)
    # Running health never mutates orchestration state or worktrees.
    assert orphan.is_dir()
    assert (tmp_path / ".harness" / "orchestration" / "state" / "ledger.json").is_file()


def test_health_json_skips_the_orchestration_group_without_the_capability(
    tmp_path: Path,
) -> None:
    """Проверить, что группа проверок оркестрации пропускается при отсутствии соответствующей возможности."""
    _init_repo(tmp_path)
    _write_lock(tmp_path, [])

    _, data = _run_health_json(tmp_path)

    checks_by_id = {check["id"]: check for check in data["checks"]}
    for check_id in _ORCHESTRATION_CHECK_IDS:
        assert checks_by_id[check_id]["status"] == "skipped"
