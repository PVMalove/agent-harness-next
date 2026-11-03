"""`harness init|adopt|update` write the generated `.harness/hook-policy.json` (ADR 0024, section 3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.json_types import JsonObject
from tests.core.test_uninstall import ROOT, git, harness

POLICY_FILE = ".harness/hook-policy.json"
PROJECT_JSON = ".harness/project.json"
HOOK_TEMPLATES = ROOT / "harness" / "project" / "hooks"
GOLDEN = (
    ROOT
    / "native/harness-runtime/crates/supervisor/tests/fixtures/hook_policy_golden.json"
)
# The critical rows of the hook matrix, ADR 0024 section 2a.
CRITICAL_GUARDS = [
    "block-dangerous-git",
    "block-direct-master",
    "block-pr-merge",
    "block-public-attribution",
    "block-scratch-outside-docs-tasks",
    "check-branch-name",
    "check-worktree-branch-name",
    "protect-hook-policy",
    "require-qa-gate",
    "test-author-guard",
]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    return root


def golden(name: str) -> JsonObject:
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["normalized"]
    case: JsonObject = next(item for item in cases if item["name"] == name)
    return case


def install(repo: Path) -> str:
    result = harness("init", str(repo), "--capability", "engineering-suite")
    assert result.returncode == 0, result.stderr
    return result.stdout


def update(repo: Path) -> str:
    result = harness("update", str(repo))
    assert result.returncode == 0, result.stderr
    return result.stdout


def set_hook_policy(repo: Path, value: object) -> None:
    path = repo / PROJECT_JSON
    data = json.loads(path.read_text(encoding="utf-8"))
    data["hook_policy"] = value
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def policy_file(repo: Path) -> JsonObject:
    document: JsonObject = json.loads((repo / POLICY_FILE).read_bytes().decode("utf-8"))
    return document


def test_init_writes_the_effective_policy_of_the_default_configuration(
    repo: Path,
) -> None:
    stdout = install(repo)

    raw = (repo / POLICY_FILE).read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.endswith(b"\n")
    assert b"\r" not in raw
    document = json.loads(raw.decode("utf-8"))
    absent = golden("absent")
    assert set(document) == {
        "schema",
        "policy",
        "hook_policy_sha256",
        "critical_guards",
        "hook_versions",
    }
    assert document["schema"] == 1
    assert document["policy"] == absent["normalized"]
    assert document["hook_policy_sha256"] == absent["sha256"]
    assert document["critical_guards"] == CRITICAL_GUARDS
    assert document["hook_versions"] == {
        f".claude/hooks/{path.name}": hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(HOOK_TEMPLATES.iterdir())
        if path.is_file() and path.suffix in {".sh", ".py"}
    }
    assert (
        f"hooks policy: {POLICY_FILE}: written hook_policy_sha256={absent['sha256']}"
        in stdout
    )


@pytest.mark.parametrize(
    "name", ["reordered-and-duplicated-escalations", "non-ascii-and-astral-paths"]
)
def test_update_writes_the_normalized_policy_and_its_digest(
    repo: Path, name: str
) -> None:
    install(repo)
    case = golden(name)
    set_hook_policy(repo, case["policy"])

    stdout = update(repo)

    document = policy_file(repo)
    assert document["policy"] == case["normalized"]
    assert document["hook_policy_sha256"] == case["sha256"]
    assert f"written hook_policy_sha256={case['sha256']}" in stdout


def test_non_ascii_paths_are_written_as_utf8_text(repo: Path) -> None:
    install(repo)
    set_hook_policy(repo, golden("non-ascii-and-astral-paths")["policy"])

    update(repo)

    assert "путь/*" in (repo / POLICY_FILE).read_bytes().decode("utf-8")


def test_a_repeated_update_leaves_the_file_byte_identical(repo: Path) -> None:
    install(repo)
    set_hook_policy(repo, golden("reordered-and-duplicated-escalations")["policy"])
    update(repo)
    before = (repo / POLICY_FILE).read_bytes()
    stamp = (repo / POLICY_FILE).stat().st_mtime_ns

    stdout = update(repo)

    assert (repo / POLICY_FILE).read_bytes() == before
    assert (repo / POLICY_FILE).stat().st_mtime_ns == stamp
    assert f"hooks policy: {POLICY_FILE}: unchanged" in stdout


def test_adopt_writes_the_policy_file(repo: Path) -> None:
    result = harness("adopt", str(repo), "--capability", "engineering-suite")

    assert result.returncode == 0, result.stderr
    assert policy_file(repo)["hook_policy_sha256"] == golden("absent")["sha256"]


def test_an_invalid_hook_policy_exits_2_and_keeps_the_file(repo: Path) -> None:
    install(repo)
    before = (repo / POLICY_FILE).read_bytes()
    set_hook_policy(repo, {"profile": "lenient"})

    result = harness("update", str(repo))

    assert result.returncode == 2, result.stdout + result.stderr
    assert "hook_policy" in result.stderr
    assert "REMEDY:" in result.stderr
    assert (repo / POLICY_FILE).read_bytes() == before
