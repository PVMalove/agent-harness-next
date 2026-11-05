"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from harness.console import repo_map as console_repo_map
from harness.console.export import export_text, render_markdown
from harness.console.repo_map import RepoMapView
from tests.console._console_repo_map_fixture import (
    HUB,
    map_payload,
)


class _RecordingRunner:
    def __init__(self, result: "subprocess.CompletedProcess[str]") -> None:
        self.result = result
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        self.calls.append((list(argv), cwd))
        return self.result


def _completed(
    stdout: str = "", stderr: str = "", code: int = 0
) -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess(["repo_map"], code, stdout, stderr)


def _view(commit: str = "f" * 40) -> RepoMapView:
    view = console_repo_map.parse_map(map_payload(commit), origin="кэш")
    assert not isinstance(view, str)
    return view


def test_parse_map_rejects_a_payload_outside_schema_v1() -> None:
    payload = map_payload("f" * 40)
    payload["extra_field_outside_v1"] = True
    files = payload["files"]
    assert isinstance(files, list)
    files[0]["owner"] = "not in schema"

    problem = console_repo_map.parse_map(payload, origin="построена")

    assert isinstance(problem, str)
    assert "схеме v1" in problem


def test_build_argv_prefers_the_installed_cli(tmp_path: Path) -> None:
    argv = console_repo_map.build_argv(tmp_path, "f" * 40)
    assert argv[:2] == [sys.executable, "-B"]
    assert argv[2].endswith(str(Path("harness") / "repo_map" / "repo_map.py"))
    assert argv[3:] == ["--repo", str(tmp_path), "--commit", "f" * 40]

    installed = tmp_path / ".harness" / "repo_map" / "repo_map.py"
    installed.parent.mkdir(parents=True)
    installed.write_text("", "utf-8")
    assert console_repo_map.build_argv(tmp_path, "f" * 40)[2] == str(installed)


def test_build_map_runs_the_cli_through_the_runner(tmp_path: Path) -> None:
    commit = "f" * 40
    runner = _RecordingRunner(_completed(json.dumps(map_payload(commit))))

    view = console_repo_map.build_map(tmp_path, commit, runner)

    assert not isinstance(view, str)
    assert view.origin == "построена"
    assert runner.calls == [(console_repo_map.build_argv(tmp_path, commit), tmp_path)]


def test_build_map_reports_cli_failure_invalid_json_and_contract_drift(
    tmp_path: Path,
) -> None:
    failed = console_repo_map.build_map(
        tmp_path,
        "f" * 40,
        _RecordingRunner(
            _completed(stderr="error: bad commit\nremedy: pass HEAD", code=2)
        ),
    )
    assert isinstance(failed, str)
    assert "кодом 2" in failed and "remedy: pass HEAD" in failed

    not_json = console_repo_map.build_map(
        tmp_path, "f" * 40, _RecordingRunner(_completed("{"))
    )
    assert isinstance(not_json, str) and "не JSON" in not_json

    drift = console_repo_map.build_map(
        tmp_path,
        "f" * 40,
        _RecordingRunner(_completed(json.dumps({"schema_version": 2}))),
    )
    assert isinstance(drift, str) and "схеме v1" in drift


def test_summary_has_tier_reason_commit_counts_and_provenance() -> None:
    view = _view()
    summary = console_repo_map.summary_lines(view)
    assert "tier: full (parser: bundle)" in summary
    assert "причина деградации: parser bundle applied" in summary
    assert f"commit: {'f' * 40}" in summary
    assert "файлов: 4" in summary
    assert "рёбер: 4" in summary
    assert "токенов (оценка): 512" in summary

    provenance = console_repo_map.provenance_lines(view)
    assert "bundle_source: local-cache" in provenance
    assert f"grammar: python@0.23.6 abi=14 sha256={'12' * 32}" in provenance


def test_symbol_search_matches_signatures_case_insensitively() -> None:
    view = _view()
    assert [
        item.path for item in console_repo_map.search_files(view, "LOAD_config")
    ] == [HUB]
    assert [item.path for item in console_repo_map.search_files(view, "main")] == [
        "pkg/cli.py"
    ]
    assert console_repo_map.search_files(view, "absent") == []
    assert len(console_repo_map.search_files(view, "  ")) == 4


def test_relations_group_by_direction_kind_and_confidence() -> None:
    view = _view()
    groups = [
        (group.direction, group.kind, group.confidence, group.paths)
        for group in console_repo_map.relations(view, HUB)
    ]
    assert groups == [
        ("исходящие", "unique-name-ref", "medium", ("pkg/cli.py",)),
        ("входящие", "import", "high", ("pkg/cli.py",)),
        ("входящие", "unique-name-ref", "medium", ("pkg/cli.py",)),
        ("входящие", "ambiguous-name-ref", "low", ("pkg/broken.py",)),
    ]
    assert console_repo_map.relations_text(view, "README.md") == "README.md\nсвязей нет"


def test_hubs_rank_by_distinct_incoming_neighbours() -> None:
    view = _view()
    assert console_repo_map.hubs(view) == [(HUB, 2), ("pkg/cli.py", 1)]
    assert console_repo_map.hubs(view, limit=1) == [(HUB, 2)]


def test_diagnostics_and_file_labels() -> None:
    view = _view()
    assert console_repo_map.diagnostics_text(view) == "syntax_error: pkg/broken.py"
    assert console_repo_map.file_label(view.files[2]) == "broken.py [syntax_error]"
    minimal = console_repo_map.parse_map(
        map_payload("f" * 40, tier="minimal"), origin="кэш"
    )
    assert not isinstance(minimal, str)
    assert console_repo_map.file_label(minimal.files[0]) == "core.py"
    assert console_repo_map.diagnostics_text(minimal) == "диагностик нет"
    assert console_repo_map.hubs_text(minimal) == "рёбер нет — хабов нет"


def test_markdown_document_and_json_export(tmp_path: Path) -> None:
    view = _view()
    text = render_markdown(console_repo_map.map_document(view))
    assert text.startswith(f"# Repo Map {'f' * 12}\n")
    assert "- **Tier:** full (bundle)" in text
    assert "## Хабы (входящая степень)" in text
    assert "    def load_config(path)" in text
    assert "pkg/cli.py -> pkg/core.py (import, high)" in text

    path = export_text(
        tmp_path,
        console_repo_map.map_json(view),
        slug=console_repo_map.export_slug(view),
        suffix=".json",
        now=datetime(2026, 9, 27, 18, 5, 9, tzinfo=UTC),
    )
    assert path == (
        tmp_path
        / "docs"
        / "tasks"
        / "console-exports"
        / f"2026-09-27-180509-repo-map-{'f' * 12}.json"
    )
    assert json.loads(path.read_text("utf-8")) == map_payload("f" * 40)


def test_summary_fields_carry_the_mockup_labels_and_the_real_values() -> None:
    view = _view()
    fields = console_repo_map.summary_fields(view)
    assert [label for label, _ in fields] == [
        "tier",
        "Деградация",
        "commit",
        "Файлов",
        "Рёбер",
        "Токенов (оценка)",
        "Источник",
    ]
    values = dict(fields)
    assert values["tier"] == "full (parser: bundle)"
    assert values["Деградация"] == "parser bundle applied"
    assert values["commit"] == "f" * 40
    assert (values["Файлов"], values["Рёбер"], values["Токенов (оценка)"]) == (
        "4",
        "4",
        "512",
    )
    assert values["Источник"] == "кэш"


def _shown(item: console_repo_map.MapFile) -> str | None:
    status = console_repo_map.file_status(item)
    return status.render("ru") if status else None


def test_file_status_is_a_symbol_and_the_parser_word_and_absent_without_a_parser() -> (
    None
):
    view = _view()
    ok, _, broken, _ = view.files
    assert _shown(ok) == "✔ ok"
    assert _shown(broken) == "✖ syntax_error"
    assert _shown(replace(ok, parser_status="too_large")) == "⚠ too_large"
    assert _shown(replace(ok, parser_status="odd")) == "⚠ odd"
    assert _shown(replace(ok, parser_status=None)) is None


def test_relation_counts_add_up_the_paths_of_each_direction() -> None:
    view = _view()
    assert console_repo_map.relation_counts(view, HUB) == (2, 1)
    assert console_repo_map.relation_counts(view, "README.md") == (0, 0)


def test_diagnostic_rows_pair_each_code_with_a_warning_status() -> None:
    view = _view()
    [(status, code, path)] = console_repo_map.diagnostic_rows(view)
    assert status.render("ru") == "⚠ syntax_error"
    assert (code, path) == ("syntax_error", "pkg/broken.py")
