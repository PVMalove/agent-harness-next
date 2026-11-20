"""Tests for the shared project contract used by test-author activation."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from harness.health import project_files
from harness.configuration_schema import value_problems

SCHEMA = (
    Path(project_files.__file__).resolve().parents[1]
    / "project"
    / "project.schema.json"
)


def test_test_author_runner_settings_are_optional_but_explicit() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert "test_paths" not in project_files.PROJECT_JSON_REQUIRED_FIELDS
    assert "test_runner" not in project_files.PROJECT_JSON_REQUIRED_FIELDS
    assert "test_paths" in project_files.PROJECT_JSON_ALLOWED_FIELDS
    assert "test_runner" in project_files.PROJECT_JSON_ALLOWED_FIELDS
    assert "glob" in schema["properties"]["test_paths"]["description"]
    assert "command" in schema["properties"]["test_runner"]["description"]
    assert (
        "{test_id}"
        in schema["properties"]["test_runner"]["properties"]["command"]["description"]
    )


def test_absent_test_author_settings_do_not_fail_health(tmp_path: Path) -> None:
    config = {
        "language": "ru",
        "base_branch": "main",
        "branch_pattern": "^feature/.+",
        "qa_gate_commands": [],
    }
    config_path = tmp_path / ".harness" / "project.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps(config), encoding="utf-8")
    problems: list[str] = []

    project_files.validate_project_json(tmp_path, problems)

    assert problems == []


@pytest.mark.parametrize(
    "profile,valid",
    [
        ({"runtime": "claude", "model": "project-model", "effort": "high"}, True),
        ({"runtime": "codex", "model": "project-model", "effort": "medium"}, True),
        ({"runtime": "claude", "model": "project-model"}, False),
        ({"runtime": "claude", "model": "bad model", "effort": "high"}, False),
        ({"runtime": "claude", "model": "m", "effort": "invented"}, False),
    ],
)
def test_author_executor_schema_matches_project_validation(
    profile: object, valid: bool
) -> None:
    config = {
        "language": "ru",
        "base_branch": "main",
        "branch_pattern": "^feature/.+",
        "qa_gate_commands": [],
        "test_author": profile,
    }
    problems: list[str] = []
    project_files.validate_project_data(config, problems)
    schema = json.loads(SCHEMA.read_text())

    assert (not problems) is valid
    assert (not value_problems(config, schema, schema)) is valid
