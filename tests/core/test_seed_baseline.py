"""`harness init|update|diff` keep a sha256 baseline of seed files in `.harness/harness.lock`."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
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


BACKUPS = ".harness/.sandboxes/seed-backups"
HOOK = ".claude/hooks/block-dangerous-git.sh"
SETTINGS = ".claude/settings.local.json"


def backup_dir(repo: Path) -> Path:
    """The one backup directory of the run; its name is a UTC time without colons."""
    (directory,) = (repo / BACKUPS).iterdir()
    assert re.fullmatch(r"\d{8}T\d{6}Z(-\d+)?", directory.name), directory.name
    return directory


def test_force_seed_file_backs_up_a_modified_file_before_replacing_it(
    repo: Path,
) -> None:
    template = (repo / RULE).read_bytes()
    (repo / RULE).write_bytes(b"# local edit\n")

    result = harness("update", str(repo), "--force-seed-file", RULE)

    assert result.returncode == 0, result.stderr
    assert (repo / RULE).read_bytes() == template
    directory = backup_dir(repo)
    assert (directory / RULE).read_bytes() == b"# local edit\n"
    assert directory.relative_to(repo).as_posix() in result.stdout
    assert seed_files(repo)[RULE] == sha(template)


@pytest.mark.parametrize("flag", ["--force-seed-files", "--force"])
def test_force_flags_back_up_every_differing_seed_file(repo: Path, flag: str) -> None:
    (repo / RULE).write_bytes(b"# local edit\n")
    (repo / SETTINGS).write_text('{"permissions": {}}\n', encoding="utf-8")
    unchanged = ".claude/rules/karpathy-guidelines.md"

    result = harness("update", str(repo), flag)

    assert result.returncode == 0, result.stderr
    directory = backup_dir(repo)
    assert (directory / RULE).read_bytes() == b"# local edit\n"
    assert (directory / SETTINGS).read_text(encoding="utf-8") == '{"permissions": {}}\n'
    assert not (directory / unchanged).exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bit")
def test_hook_backup_keeps_the_executable_bit(repo: Path) -> None:
    (repo / HOOK).write_bytes(b"#!/bin/sh\necho local\n")
    (repo / HOOK).chmod(0o755)

    result = harness("update", str(repo), "--force-seed-file", HOOK)

    assert result.returncode == 0, result.stderr
    saved = backup_dir(repo) / HOOK
    assert saved.read_bytes() == b"#!/bin/sh\necho local\n"
    assert saved.stat().st_mode & stat.S_IXUSR
    assert (repo / HOOK).stat().st_mode & stat.S_IXUSR


def test_failed_backup_fails_the_command_and_keeps_the_file(repo: Path) -> None:
    (repo / RULE).write_bytes(b"# local edit\n")
    (repo / BACKUPS).parent.mkdir(parents=True, exist_ok=True)
    (repo / BACKUPS).write_text("not a directory", encoding="utf-8")

    result = harness("update", str(repo), "--force-seed-file", RULE)

    assert result.returncode == 1
    assert "back up" in result.stderr
    assert (repo / RULE).read_bytes() == b"# local edit\n"


def test_update_replaces_an_outdated_seed_file_with_a_backup(repo: Path) -> None:
    template = make_outdated(repo)

    result = harness("update", str(repo))

    assert result.returncode == 0, result.stderr
    assert (repo / RULE).read_bytes() == template
    directory = backup_dir(repo)
    assert (directory / RULE).read_bytes() == OLD_BYTES
    assert directory.relative_to(repo).as_posix() in result.stdout
    assert seed_files(repo)[RULE] == sha(template)
    assert "--record-seed-baseline" not in result.stdout


def test_update_keeps_a_locally_modified_seed_file_and_names_it(repo: Path) -> None:
    (repo / RULE).write_bytes(b"# local edit\n")
    entry = seed_files(repo)[RULE]

    result = harness("update", str(repo))

    assert result.returncode == 0, result.stderr
    assert (repo / RULE).read_bytes() == b"# local edit\n"
    assert seed_files(repo)[RULE] == entry
    assert not (repo / BACKUPS).exists()
    assert f"--force-seed-file {RULE}" in result.stdout
    assert "отличаются от шаблонов upstream" not in result.stdout


def test_update_without_a_baseline_keeps_differing_files_and_hints_the_record_flag(
    repo: Path,
) -> None:
    lock = load_lock(repo)
    del lock["seed_files"]
    save_lock(repo, lock)
    (repo / RULE).write_bytes(b"# 1.x seed\n")

    result = harness("update", str(repo))

    assert result.returncode == 0, result.stderr
    assert (repo / RULE).read_bytes() == b"# 1.x seed\n"
    assert not (repo / BACKUPS).exists()
    assert f"harness update {repo} --record-seed-baseline" in result.stdout
    recorded = seed_files(repo)
    assert RULE not in recorded
    hook = ".claude/hooks/block-dangerous-git.sh"
    assert recorded[hook] == sha((repo / hook).read_bytes())


def test_record_seed_baseline_writes_hash_or_null_and_changes_no_file(
    repo: Path,
) -> None:
    lock = load_lock(repo)
    kept = ".claude/rules/karpathy-guidelines.md"
    lock["seed_files"] = {kept: sha(b"an earlier baseline")}
    save_lock(repo, lock)
    (repo / RULE).write_bytes(b"# 1.x seed\n")
    hook = ".claude/hooks/block-dangerous-git.sh"
    before = {
        path: path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts and path.name != "harness.lock"
    }

    result = harness("update", str(repo), "--record-seed-baseline")

    assert result.returncode == 0, result.stderr
    after = {
        path: path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts and path.name != "harness.lock"
    }
    assert after == before
    recorded = seed_files(repo)
    assert recorded[RULE] is None
    assert recorded[hook] == sha((repo / hook).read_bytes())
    assert recorded[kept] == sha(b"an earlier baseline")

    update = harness("update", str(repo))

    assert update.returncode == 0, update.stderr
    assert (repo / RULE).read_bytes() == b"# 1.x seed\n"
    assert f"--force-seed-file {RULE}" in update.stdout
    assert "--record-seed-baseline" not in update.stdout


@pytest.mark.parametrize(
    "flag",
    [["--force"], ["--force-managed-files"], ["--force-seed-files"], ["--force-seed-file", RULE]],
)
def test_record_seed_baseline_refuses_force_flags(repo: Path, flag: list[str]) -> None:
    lock_before = (repo / LOCK).read_bytes()

    result = harness("update", str(repo), "--record-seed-baseline", *flag)

    assert result.returncode != 0
    assert "--record-seed-baseline" in result.stderr
    assert (repo / LOCK).read_bytes() == lock_before


def test_diff_reports_the_seed_groups_and_keeps_their_union(repo: Path) -> None:
    make_outdated(repo)
    modified = ".claude/rules/karpathy-guidelines.md"
    (repo / modified).write_bytes(b"# local edit\n")
    unbaselined = ".claude/hooks/block-dangerous-git.sh"
    (repo / unbaselined).write_bytes(b"#!/bin/sh\n# 1.x hook\n")
    lock = load_lock(repo)
    del lock["seed_files"][unbaselined]
    save_lock(repo, lock)

    data = json.loads(harness("diff", str(repo), "--json").stdout)

    assert data["seed_outdated"] == [RULE]
    assert data["seed_modified"] == [modified]
    assert data["seed_unbaselined"] == [unbaselined]
    assert data["seed_differing"] == sorted([RULE, modified, unbaselined])

    text = harness("diff", str(repo)).stdout
    assert f"seed_differing: {RULE} (устарел по версии)" in text
    assert f"seed_differing: {modified} (изменён локально)" in text
    assert f"seed_differing: {unbaselined} (без baseline)" in text
    assert f"--force-seed-file {modified}" in text
    assert "--record-seed-baseline" in text
