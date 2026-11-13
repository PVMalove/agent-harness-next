"""Merge proof for deleting an issue branch: harness/project/hooks/merged_branch.py."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Callable

import pytest

HOOKS = Path(__file__).resolve().parents[2] / "harness" / "project" / "hooks"
BRANCH = "feature/issue-7-cleanup"
SHA = "a" * 40
OTHER_SHA = "b" * 40


@pytest.fixture(scope="module")
def merged_branch() -> ModuleType:
    bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(HOOKS))
    try:
        spec = importlib.util.spec_from_file_location(
            "merged_branch_test", HOOKS / "merged_branch.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["merged_branch_test"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = bytecode
        sys.path.remove(str(HOOKS))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "project.json").write_text(
        json.dumps(
            {"base_branch": "develop", "branch_pattern": "^feature/issue-[0-9]+-.+"}
        ),
        encoding="utf-8",
    )
    return tmp_path


def _resolve(kind: str = "github") -> Callable[[Path], SimpleNamespace]:
    def resolve(repo: Path) -> SimpleNamespace:
        return SimpleNamespace(
            effective=SimpleNamespace(type=kind, host="example.test", project="o/r")
        )

    return resolve


class FakeRun:
    """Tracker CLI stand-in: records argv, answers with one fixed result."""

    def __init__(
        self, stdout: str = "[]", returncode: int = 0, none: bool = False
    ) -> None:
        self.calls: list[list[str]] = []
        self.stdout, self.returncode, self.none = stdout, returncode, none

    def __call__(self, argv: list[str]) -> subprocess.CompletedProcess[str] | None:
        self.calls.append(argv)
        if self.none:
            return None
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, "")


def _which(name: str) -> str | None:
    return "/usr/bin/" + name


def _reason(
    module: ModuleType,
    project: Path,
    run: FakeRun,
    kind: str = "github",
    branch: str = BRANCH,
    which: Callable[[str], str | None] = _which,
) -> str:
    reason: str = module.merge_block_reason(
        project, branch, SHA, run=run, resolve=_resolve(kind), which=which
    )
    return reason


def test_a_merged_github_pr_with_the_branch_head_allows(
    merged_branch: ModuleType, project: Path
) -> None:
    run = FakeRun(json.dumps([{"number": 3, "state": "MERGED", "headRefOid": SHA}]))
    assert _reason(merged_branch, project, run) == ""
    argv = run.calls[0]
    assert argv[:3] == ["/usr/bin/gh", "pr", "list"]
    assert ["-R", "example.test/o/r"] == argv[argv.index("-R") : argv.index("-R") + 2]
    assert argv[argv.index("--head") + 1] == BRANCH
    assert argv[argv.index("--state") + 1] == "merged"


def test_a_merged_pr_with_another_head_blocks(
    merged_branch: ModuleType, project: Path
) -> None:
    run = FakeRun(
        json.dumps([{"number": 3, "state": "MERGED", "headRefOid": OTHER_SHA}])
    )
    reason = _reason(merged_branch, project, run)
    assert SHA in reason and OTHER_SHA in reason


@pytest.mark.parametrize(
    "answer",
    [
        [],
        [{"number": 3, "state": "OPEN", "headRefOid": SHA}],
        [{"number": 3, "state": "CLOSED", "headRefOid": SHA}],
    ],
    ids=["no-pr", "open", "closed-unmerged"],
)
def test_a_branch_without_a_merged_pr_blocks(
    merged_branch: ModuleType, project: Path, answer: list[dict[str, str]]
) -> None:
    assert _reason(merged_branch, project, FakeRun(json.dumps(answer)))


@pytest.mark.parametrize(
    "branch",
    ["master", "main", "develop", "integration/epic", "other-branch"],
)
def test_a_protected_or_foreign_branch_blocks_without_the_tracker(
    merged_branch: ModuleType, project: Path, branch: str
) -> None:
    run = FakeRun(json.dumps([{"state": "MERGED", "headRefOid": SHA}]))
    assert _reason(merged_branch, project, run, branch=branch)
    assert run.calls == []


def test_a_project_without_branch_pattern_blocks(
    merged_branch: ModuleType, tmp_path: Path
) -> None:
    run = FakeRun(json.dumps([{"state": "MERGED", "headRefOid": SHA}]))
    assert _reason(merged_branch, tmp_path, run)
    assert run.calls == []


@pytest.mark.parametrize(
    "run",
    [FakeRun(returncode=1), FakeRun(none=True), FakeRun(stdout="not json")],
    ids=["cli-error", "timeout", "unparsed"],
)
def test_an_unanswering_tracker_blocks(
    merged_branch: ModuleType, project: Path, run: FakeRun
) -> None:
    assert _reason(merged_branch, project, run)


def test_a_missing_tracker_cli_blocks(merged_branch: ModuleType, project: Path) -> None:
    run = FakeRun(json.dumps([{"state": "MERGED", "headRefOid": SHA}]))
    assert _reason(merged_branch, project, run, which=lambda name: None)
    assert run.calls == []


def test_a_local_tracker_blocks(merged_branch: ModuleType, project: Path) -> None:
    run = FakeRun(json.dumps([{"state": "MERGED", "headRefOid": SHA}]))
    assert _reason(merged_branch, project, run, kind="local")
    assert run.calls == []


def test_a_missing_resolver_blocks(merged_branch: ModuleType, project: Path) -> None:
    assert merged_branch.merge_block_reason(project, BRANCH, SHA)


def test_a_merged_gitlab_mr_with_the_branch_head_allows(
    merged_branch: ModuleType, project: Path
) -> None:
    run = FakeRun(json.dumps([{"iid": 4, "state": "merged", "sha": SHA}]))
    assert _reason(merged_branch, project, run, kind="gitlab") == ""
    argv = run.calls[0]
    assert argv[:3] == ["/usr/bin/glab", "mr", "list"]
    assert "https://example.test/o/r" in argv
    assert argv[argv.index("--source-branch") + 1] == BRANCH
    assert "--merged" in argv


def test_a_merged_gitlab_mr_with_another_head_blocks(
    merged_branch: ModuleType, project: Path
) -> None:
    run = FakeRun(json.dumps([{"iid": 4, "state": "merged", "sha": OTHER_SHA}]))
    assert _reason(merged_branch, project, run, kind="gitlab")
