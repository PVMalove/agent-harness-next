"""`harness init|update|diff` keep a sha256 baseline of seed files in `.harness/harness.lock`."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.core.test_uninstall import git, harness

LOCK = ".harness/harness.lock"
SEED_FOLDERS = ("docs/agents", ".claude/hooks", ".claude/rules", ".claude/agents")
RUNTIME_CONFIGS = (".claude/settings.local.json", ".codex/hooks.json")
RULE = ".claude/rules/token-efficiency.md"
OLD_BYTES = b"# old seed release\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    result = harness("init", str(root), "--capability", "engineering-suite")
    assert result.returncode == 0, result.stderr
    return root


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_lock(repo: Path) -> JsonObject:
    lock: JsonObject = json.loads((repo / LOCK).read_text(encoding="utf-8"))
    return lock


def save_lock(repo: Path, lock: JsonObject) -> None:
    (repo / LOCK).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def seed_files(repo: Path) -> dict[str, str | None]:
    value: dict[str, str | None] = load_lock(repo)["seed_files"]
    return value


def make_outdated(repo: Path, relative: str = RULE) -> bytes:
    """Write "old release" bytes into a seed file and record them as its baseline."""
    template = (repo / relative).read_bytes()
    (repo / relative).write_bytes(OLD_BYTES)
    lock = load_lock(repo)
    lock["seed_files"][relative] = sha(OLD_BYTES)
    save_lock(repo, lock)
    return template


def test_init_records_the_sha256_of_every_seed_file(repo: Path) -> None:
    recorded = seed_files(repo)

    expected = {
        path.relative_to(repo).as_posix()
        for folder in SEED_FOLDERS
        for path in (repo / folder).iterdir()
        if path.is_file()
    }
    expected |= {
        ".harness/.gitignore",
        ".harness/project.schema.json",
        ".harness/.sandboxes/scratch/.gitignore",
    }
    assert set(recorded) == expected
    for relative, value in recorded.items():
        assert value == sha((repo / relative).read_bytes()), relative
    for excluded in (*RUNTIME_CONFIGS, ".harness/project.json"):
        assert excluded not in recorded
    assert load_lock(repo)["schema"] == 1


def test_update_keeps_the_seed_baseline(repo: Path) -> None:
    before = seed_files(repo)

    result = harness("update", str(repo))

    assert result.returncode == 0, result.stderr
    assert seed_files(repo) == before


@pytest.mark.parametrize(
    "value",
    [["not", "an", "object"], {"../x.md": None}, {RULE: "NOT-HEX"}],
    ids=["not-object", "parent-path", "not-hex"],
)
def test_malformed_seed_baseline_fails_update_before_any_write(
    repo: Path, value: object
) -> None:
    lock = load_lock(repo)
    lock["seed_files"] = value
    save_lock(repo, lock)
    (repo / RULE).write_bytes(OLD_BYTES)
    lock_before = (repo / LOCK).read_bytes()

    result = harness("update", str(repo))

    assert result.returncode == 1
    assert "seed_files" in result.stderr
    assert (repo / LOCK).read_bytes() == lock_before
    assert (repo / RULE).read_bytes() == OLD_BYTES
