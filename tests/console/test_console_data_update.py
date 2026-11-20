"""Diff rendering and CLI response parsing with injected package and process data."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.console.kernel import data

RULES = ".claude/rules/token-efficiency.md"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / RULES
    path.parent.mkdir(parents=True)
    # Bytes: on Windows `write_text` writes CRLF, and the file would no longer match the template.
    path.write_bytes(b"managed rule\n")
    monkeypatch.setattr(
        data,
        "_packager",
        lambda: {
            "load_lock": lambda _repo: None,
            "seed_template_files": lambda _repo, **_kwargs: {RULES: b"managed rule\n"},
        },
    )
    return tmp_path


@pytest.mark.parametrize("state", ["clean", "missing"])
def test_drift_report_parses_the_cli_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    import json

    def run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert argv[-3:] == ["diff", str(tmp_path), "--json"]
        assert kwargs["timeout"] == 30.0
        return subprocess.CompletedProcess(argv, 0, json.dumps({"state": state}), "")

    monkeypatch.setattr(subprocess, "run", run)
    assert data.drift_report(tmp_path) == {"state": state}
    assert data.drift_state(tmp_path) == state


@pytest.mark.parametrize(
    "outcome",
    [OSError("no python"), subprocess.TimeoutExpired("harness", 30), "not json"],
)
def test_drift_report_is_none_without_a_readable_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: object
) -> None:
    def fake(*_args: object, **_kwargs: object) -> object:
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess([], 0, str(outcome), "")

    monkeypatch.setattr(subprocess, "run", fake)
    assert data.drift_report(tmp_path) is None
    assert data.drift_state(tmp_path) == "неизвестно"


def test_update_diff_text_shows_a_seed_file_against_its_template(project: Path) -> None:
    path = project / RULES
    path.write_text("managed rule\nLOCAL\n", encoding="utf-8")
    text = data.update_diff_text(project, RULES)
    assert text.startswith(f"--- проект/{RULES}\n+++ после обновления/{RULES}")
    assert "-LOCAL" in text


def test_a_file_that_matches_what_the_update_writes_has_an_empty_diff(
    project: Path,
) -> None:
    assert data.update_diff_text(project, RULES) == ""
    assert data.update_diff_text(project, "no/such/file.md") == ""


def test_a_binary_file_has_no_diff(project: Path) -> None:
    (project / RULES).write_bytes(b"\xff\xfe\x00binary")
    assert "diff недоступен" in data.update_diff_text(project, RULES)
