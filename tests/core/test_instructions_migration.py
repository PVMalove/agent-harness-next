"""`harness update` moves agent instructions of older installs to their current places: managed
instructions from `.harness/docs/` (#814), seed guides from `docs/agents/` and the Technical English
contract from `.harness/instructions/` to the language rules in `.claude/rules/` (#1249)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.json_types import JsonObject

from tests.core.test_uninstall import git, harness

LANGUAGE_RULES = (".claude/rules/technical-english.md", ".claude/rules/technical-russian.md")
OLD_CONTRACT = ".harness/instructions/technical-english.md"


def _lock(root: Path) -> JsonObject:
    lock: JsonObject = json.loads((root / ".harness/harness.lock").read_text(encoding="utf-8"))
    return lock


def _write_lock(root: Path, lock: JsonObject) -> None:
    (root / ".harness/harness.lock").write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def _installed(tmp_path: Path, *capabilities: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    args = [arg for name in capabilities for arg in ("--capability", name)]
    result = harness("init", str(root), *args)
    assert result.returncode == 0, result.stderr
    return root


@pytest.fixture
def pre_814(tmp_path: Path) -> Path:
    """A project installed before #814: a managed instruction is in `.harness/docs/`."""
    root = _installed(tmp_path, "engineering-suite")
    lock = _lock(root)
    (root / ".harness/docs").mkdir()
    new, old = ".harness/instructions/project-memory.md", ".harness/docs/project-memory.md"
    (root / new).rename(root / old)
    lock["files"][old] = lock["files"].pop(new)
    _write_lock(root, lock)
    return root


@pytest.fixture
def pre_1249(tmp_path: Path) -> Path:
    """A project installed before #1249: seed guides in `docs/agents/`, the Technical English
    contract a managed instruction, no language rules."""
    root = _installed(tmp_path, "engineering-suite")
    lock = _lock(root)
    (root / "docs/agents").mkdir(parents=True)
    for key in [key for key in lock["seed_files"] if key.startswith(".harness/instructions/")]:
        old = "docs/agents/" + key.split("/")[-1]
        (root / key).rename(root / old)
        lock["seed_files"][old] = lock["seed_files"].pop(key)
    for rule in LANGUAGE_RULES:
        (root / rule).unlink()
        lock["files"].pop(rule)
    (root / OLD_CONTRACT).write_text("# Technical English\n", encoding="utf-8")
    lock["files"][OLD_CONTRACT] = hashlib.sha256((root / OLD_CONTRACT).read_bytes()).hexdigest()
    _write_lock(root, lock)
    return root


def test_update_moves_the_managed_instructions(pre_814: Path) -> None:
    result = harness("update", str(pre_814))

    assert result.returncode == 0, result.stderr
    assert (pre_814 / ".harness/instructions/project-memory.md").is_file()
    assert not (pre_814 / ".harness/docs/project-memory.md").exists()
    assert not [path for path in _lock(pre_814)["files"] if path.startswith(".harness/docs/")]


def test_a_fresh_install_has_language_rules_and_no_docs(tmp_path: Path) -> None:
    root = _installed(tmp_path, "engineering-suite")

    for rule in LANGUAGE_RULES:
        assert (root / rule).is_file()
    assert (root / ".harness/instructions/git-workflow.md").is_file()
    assert not (root / OLD_CONTRACT).exists()
    assert not (root / "docs").exists()


def test_the_default_install_gets_the_language_rules(tmp_path: Path) -> None:
    root = _installed(tmp_path)

    for rule in LANGUAGE_RULES:
        assert (root / rule).is_file()
        assert rule in _lock(root)["files"]


def test_update_moves_seed_guides_with_project_edits(pre_1249: Path) -> None:
    edited = pre_1249 / "docs/agents/issue-tracker.md"
    edited.write_text(edited.read_text(encoding="utf-8") + "\nLocal tracker note.\n", encoding="utf-8")

    result = harness("update", str(pre_1249))

    assert result.returncode == 0, result.stderr
    moved = pre_1249 / ".harness/instructions/issue-tracker.md"
    assert moved.read_text(encoding="utf-8").endswith("\nLocal tracker note.\n")
    assert (pre_1249 / ".harness/instructions/git-workflow.md").is_file()
    assert not (pre_1249 / "docs").exists()
    baseline = _lock(pre_1249)["seed_files"]
    assert ".harness/instructions/issue-tracker.md" in baseline
    assert not [key for key in baseline if key.startswith("docs/agents/")]
    assert "Руководства перенесены из docs/agents/" in result.stdout
    assert "изменены локально" in result.stdout


def test_update_keeps_files_harness_did_not_seed(pre_1249: Path) -> None:
    (pre_1249 / "docs/agents/domain.md").write_text("# Domain\n", encoding="utf-8")

    result = harness("update", str(pre_1249))

    assert result.returncode == 0, result.stderr
    assert (pre_1249 / "docs/agents/domain.md").is_file()
    assert not (pre_1249 / "docs/agents/git-workflow.md").exists()
    assert "docs/agents/domain.md" in result.stdout


def test_update_keeps_a_conflicting_old_copy(pre_1249: Path) -> None:
    (pre_1249 / ".harness/instructions").mkdir(exist_ok=True)
    (pre_1249 / ".harness/instructions/artifacts.md").write_text("# New\n", encoding="utf-8")

    result = harness("update", str(pre_1249))

    assert result.returncode == 0, result.stderr
    assert (pre_1249 / "docs/agents/artifacts.md").is_file()
    assert "уже есть другой файл" in result.stdout


def test_update_installs_the_language_rules(pre_1249: Path) -> None:
    result = harness("update", str(pre_1249))

    assert result.returncode == 0, result.stderr
    for rule in LANGUAGE_RULES:
        assert (pre_1249 / rule).is_file()
    assert not (pre_1249 / OLD_CONTRACT).exists()
    assert OLD_CONTRACT not in _lock(pre_1249)["files"]
