"""Symbol kinds and the coverage of a Repo Map, derived in the kernel without changing schema v1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from harness.console.kernel.repo_map_coverage import (
    MapCoverage,
    coverage,
    excluded_files,
    file_class,
    symbol_kind,
    symbol_kinds,
)
from harness.console.kernel.repo_map_snapshot import RepoMapFacts

from ._screen_facts import repo_map_facts


@pytest.mark.parametrize(
    ("signature", "kind"),
    [
        ("def load(path: str) -> dict", "function"),
        ("async def fetch(url)", "function"),
        ("def Settings.read(self)", "method"),
        ("async def Client.call(self, name)", "method"),
        ("class Settings", "class"),
        ("class Settings(BaseModel)", "class"),
        ("function render(props): JSX.Element", "function"),
        ("async function load()", "function"),
        ("const handler(event)", "function"),
        ("method Panel.draw(ctx)", "method"),
        ("async method Panel.load()", "method"),
        ("class Panel extends Base", "class"),
        ("func Serve(addr string) error", "function"),
        ("func (s *Server) Close() error", "method"),
        ("type Server struct", "struct"),
        ("type Store interface", "interface"),
        ("constructor Repo.Repo(String path)", "method"),
        ("static method Repo.open(String path): Repo", "method"),
        ("var answer", "other"),
    ],
)
def test_each_signature_text_has_its_kind(signature: str, kind: str) -> None:
    assert symbol_kind(signature) == kind


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("harness/console/kernel/reports.py", "source"),
        ("tests/console/test_reports.py", "tests"),
        ("pkg/test_core.py", "tests"),
        ("cmd/server_test.go", "tests"),
        ("src/app.test.ts", "tests"),
        ("web/panel.spec.tsx", "tests"),
        ("src/__tests__/panel.tsx", "tests"),
        ("docs/adr/0001.md", "docs"),
        ("README.md", "docs"),
        ("guide/intro.rst", "docs"),
        ("docs/tests/notes.md", "tests"),
        ("Makefile", "source"),
    ],
)
def test_each_path_has_one_file_class(path: str, kind: str) -> None:
    assert file_class(path) == kind


def test_the_snapshot_carries_the_kinds_and_coverage_and_round_trips() -> None:
    facts = repo_map_facts()
    assert facts.view is not None
    payload = facts.to_payload()
    assert payload["symbol_kinds"] == symbol_kinds(facts.view)
    assert payload["coverage"] == {"source": 3, "docs": 1, "tests": 0, "excluded": 2}
    assert RepoMapFacts.from_payload(payload) == facts


def test_a_snapshot_without_a_map_has_no_kinds_or_coverage() -> None:
    facts = replace(repo_map_facts(), view=None, excluded=None)
    payload = facts.to_payload()
    assert (payload["symbol_kinds"], payload["coverage"]) == (None, None)
    assert RepoMapFacts.from_payload(payload) == facts


def test_derived_fields_that_disagree_with_the_map_are_refused() -> None:
    payload = repo_map_facts().to_payload()
    with pytest.raises(ValueError):
        RepoMapFacts.from_payload({**payload, "coverage": {**payload["coverage"], "docs": 9}})  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        RepoMapFacts.from_payload({**payload, "symbol_kinds": {}})


def test_excluded_counts_tracked_files_missing_from_the_map() -> None:
    view = repo_map_facts().view
    assert view is not None
    calls: list[list[str]] = []

    def run(argv: Sequence[str]) -> tuple[int, str] | None:
        calls.append(list(argv))
        return 0, "pkg/core.py\0pkg/cli.py\0vendor/lib.js\0assets/logo.png\0"

    assert excluded_files(Path("/repo"), view, run) == 2
    assert calls == [["git", "-C", "/repo", "ls-tree", "-r", "-z", "--name-only", view.commit]]
    assert excluded_files(Path("/repo"), view, lambda argv: None) is None
    assert excluded_files(Path("/repo"), view, lambda argv: (128, "")) is None
    assert coverage(view, None) == MapCoverage(3, 1, 0, None)
