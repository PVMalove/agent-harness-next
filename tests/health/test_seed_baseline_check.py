"""`harness health` check `files.seed_baseline`: the format of `seed_files` in harness.lock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.core.test_uninstall import git, harness

LOCK = ".harness/harness.lock"


def install(tmp_path: Path, capability: str) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    result = harness("init", str(root), "--capability", capability)
    assert result.returncode == 0, result.stderr
    return root


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return install(tmp_path, "engineering-suite")


def check(repo: Path) -> JsonObject:
    """The `files.seed_baseline` entry of `harness health --json`."""
    result = harness("health", str(repo), "--json")
    report = json.loads(result.stdout)
    found: JsonObject = next(
        c for c in report["checks"] if c["id"] == "files.seed_baseline"
    )
    return found


def edit_lock(repo: Path, **changes: object) -> None:
    lock = json.loads((repo / LOCK).read_text(encoding="utf-8"))
    for key, value in changes.items():
        if value is None:
            lock.pop(key, None)
        else:
            lock[key] = value
    (repo / LOCK).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def test_a_fresh_install_has_a_valid_seed_baseline(repo: Path) -> None:
    assert check(repo)["status"] == "ok"


def test_a_lock_without_seed_files_warns_with_the_record_command(repo: Path) -> None:
    edit_lock(repo, seed_files=None)

    result = check(repo)

    assert result["status"] == "warn"
    command = result["fix"]["command"]
    assert "update" in command and str(repo) in command
    assert command.endswith("--record-seed-baseline")


@pytest.mark.parametrize(
    "value",
    [
        ["not", "an", "object"],
        {"../x.md": None},
        {"/abs/x.md": None},
        {"docs\\agents\\x.md": None},
        {"docs/agents/x.md": "NOT-HEX"},
        {"docs/agents/x.md": "A" * 64},
    ],
    ids=["not-object", "parent", "absolute", "backslash", "not-hex", "upper-hex"],
)
def test_a_malformed_seed_baseline_fails(repo: Path, value: object) -> None:
    edit_lock(repo, seed_files=value)

    assert check(repo)["status"] == "fail"


def test_null_baseline_is_valid(repo: Path) -> None:
    edit_lock(repo, seed_files={"docs/agents/x.md": None})

    assert check(repo)["status"] == "ok"


def test_a_missing_lock_is_left_to_files_lock(repo: Path) -> None:
    (repo / LOCK).unlink()

    assert check(repo)["status"] == "skipped"


def test_project_foundation_installs_no_seed_files(tmp_path: Path) -> None:
    repo = install(tmp_path, "project-foundation")

    assert check(repo)["status"] == "skipped"
