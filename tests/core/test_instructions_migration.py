"""`harness update` moves the managed agent instructions of an older install from `.harness/docs/`
to `.harness/instructions/` (#814)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.core.test_uninstall import git, harness

MOVED = ("technical-english.md", "project-memory.md")


@pytest.fixture
def old_layout(tmp_path: Path) -> Path:
    """A project installed before #814: the managed instructions are in `.harness/docs/`."""
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    result = harness("init", str(root), "--capability", "engineering-suite")
    assert result.returncode == 0, result.stderr
    lock_path = root / ".harness" / "harness.lock"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    (root / ".harness" / "docs").mkdir()
    for name in MOVED:
        new = f".harness/instructions/{name}"
        old = f".harness/docs/{name}"
        (root / new).rename(root / old)
        lock["files"][old] = lock["files"].pop(new)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return root


def test_update_moves_the_managed_instructions(old_layout: Path) -> None:
    result = harness("update", str(old_layout))

    assert result.returncode == 0, result.stderr
    for name in MOVED:
        assert (old_layout / ".harness" / "instructions" / name).is_file()
        assert not (old_layout / ".harness" / "docs" / name).exists()
    lock = json.loads((old_layout / ".harness" / "harness.lock").read_text(encoding="utf-8"))
    assert not [path for path in lock["files"] if path.startswith(".harness/docs/")]


def test_the_seed_instructions_stay_in_docs_agents(old_layout: Path) -> None:
    result = harness("update", str(old_layout))

    assert result.returncode == 0, result.stderr
    assert (old_layout / "docs" / "agents" / "git-workflow.md").is_file()
    for name in MOVED:
        assert not (old_layout / "docs" / "agents" / name).exists()
