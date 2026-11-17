"""A repository without orchestration state (ADR 0036): no coordinator command creates a ledger of
versions 1-3, and ``harness-runtime init`` gives it the runtime store."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.ledger.lifecycle import LedgerError, LifecycleLedger

from .legacy_state import seed_file_ledger
from .runtime_store_support import (
    MIGRATE_APPROVAL,
    STATE_REL,
    ServingRuntime,
    add_coordinator_batch,
    coordinator_repository,
    coordinator_with,
    runtime_binary,
    tree,
)
from .runtime_store_support import coordinator as coordinator_cli

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="the Unix-socket runtime is not on Windows"
)


def _init(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(runtime_binary()), "init", "--repo", str(repo), *MIGRATE_APPROVAL],
        capture_output=True,
        text=True,
        check=False,
    )


def _refused(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 2, result.stderr
    assert result.stdout == ""
    assert result.stderr.startswith("ERROR: ")
    remedy = result.stderr.partition("REMEDY:")[2]
    assert "harness-runtime init --repo" in remedy, result.stderr
    return remedy


def _state_files(repo: Path) -> dict[str, bytes]:
    state = repo / STATE_REL
    return tree(state) if state.exists() else {}


def test_ensure_on_an_empty_state_directory_refuses_and_writes_nothing(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"

    with pytest.raises(LedgerError) as raised:
        LifecycleLedger(state).ensure()

    assert "harness-runtime init" in raised.value.remedy
    assert not state.exists()


def test_batch_create_on_a_repository_without_state_refuses_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo = coordinator_repository(tmp_path)

    with pytest.raises(CoordinatorError) as raised:
        add_coordinator_batch(
            repo, tmp_path / "worktree", ticket="#1146", dispatch=False, seed=False
        )

    assert "harness-runtime init --repo" in raised.value.remedy
    assert str(repo) in raised.value.remedy
    assert _state_files(repo) == {}
    assert not (repo / STATE_REL / "ledger.json").exists()


def test_ledger_reset_on_a_repository_without_state_refuses_and_writes_nothing(
    tmp_path: Path,
) -> None:
    repo = coordinator_repository(tmp_path)

    _refused(coordinator_cli(repo, "ledger", "reset", "--confirm", "RESET"))

    assert _state_files(repo) == {}


def test_an_existing_file_ledger_keeps_working_until_migrate(tmp_path: Path) -> None:
    repo = coordinator_repository(tmp_path)
    seed_file_ledger(repo / STATE_REL)

    ids, _ = add_coordinator_batch(
        repo, tmp_path / "worktree", ticket="#1146", dispatch=False
    )

    pointer = json.loads((repo / STATE_REL / "ledger.json").read_text(encoding="utf-8"))
    assert pointer["version"] == 3
    assert ids["batch_id"].startswith("batch-")


def test_init_gives_a_new_project_the_store_and_batch_create_writes_to_it(
    tmp_path: Path,
) -> None:
    repo = coordinator_repository(tmp_path)

    initialized = _init(repo)

    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["initialized"] is True
    runtime = ServingRuntime(repo)
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setenv("XDG_RUNTIME_DIR", runtime.environ["XDG_RUNTIME_DIR"])
            ids, _ = add_coordinator_batch(
                repo, tmp_path / "worktree", ticket="#1146", dispatch=False
            )
        listed = coordinator_with(repo, runtime, "batch", "list")
    finally:
        runtime.stop()

    pointer = json.loads((repo / STATE_REL / "ledger.json").read_text(encoding="utf-8"))
    assert pointer["version"] == 4
    assert not (repo / STATE_REL / "generations").exists()
    assert listed.returncode == 0, listed.stderr
    assert ids["batch_id"] in listed.stdout
