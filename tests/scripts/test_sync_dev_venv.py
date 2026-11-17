"""`make` never re-syncs the main checkout's venv linked into a worktree (#1188)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "sync_dev_venv.py"

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the fake uv is a shell script")


def run(checkout: Path, uv_log: Path) -> subprocess.CompletedProcess[str]:
    bin_dir = checkout.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake_uv = bin_dir / "uv"
    fake_uv.write_text(f'#!/bin/sh\necho "$@" >> {uv_log}\n', encoding="utf-8")
    fake_uv.chmod(0o755)
    return subprocess.run(
        [sys.executable, str(SCRIPT), ".harness/.venv", "python3"],
        cwd=checkout,
        env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        check=False,
    )


def checkouts(tmp_path: Path) -> tuple[Path, Path]:
    main, worktree = tmp_path / "main", tmp_path / "worktree"
    for checkout in (main, worktree):
        (checkout / ".harness").mkdir(parents=True)
        (checkout / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        (checkout / "uv.lock").write_text("lock = 1\n", encoding="utf-8")
    (main / ".harness" / ".venv").mkdir()
    (worktree / ".harness" / ".venv").symlink_to(main / ".harness" / ".venv")
    return main, worktree


def test_a_linked_venv_with_the_same_lock_is_not_synced(tmp_path: Path) -> None:
    _, worktree = checkouts(tmp_path)
    uv_log = tmp_path / "uv.log"

    result = run(worktree, uv_log)

    assert result.returncode == 0, result.stderr
    assert "no sync" in result.stdout
    assert not uv_log.exists()


def test_a_linked_venv_with_another_lock_is_refused_without_a_sync(
    tmp_path: Path,
) -> None:
    _, worktree = checkouts(tmp_path)
    (worktree / "uv.lock").write_text("lock = 2\n", encoding="utf-8")
    uv_log = tmp_path / "uv.log"

    result = run(worktree, uv_log)

    assert result.returncode == 1
    assert "uv.lock differ" in result.stderr
    assert "UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked" in result.stderr
    assert not uv_log.exists()


def test_an_own_venv_is_synced_and_stamped(tmp_path: Path) -> None:
    main, _ = checkouts(tmp_path)
    uv_log = tmp_path / "uv.log"

    result = run(main, uv_log)

    assert result.returncode == 0, result.stderr
    assert uv_log.read_text(encoding="utf-8").split() == [
        "sync", "--locked", "--python", "python3",
    ]  # fmt: skip
    assert (main / ".harness" / ".venv" / ".requirements-installed").is_file()
