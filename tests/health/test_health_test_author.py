"""Health resolves the configured author before probing the selected protected adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from harness.health import registry
from harness.health.checks import hooks
from harness.health.context import HealthContext
from harness.health.report_json import to_json
from tests.test_author.test_preflight import _project, _runner


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = _project(tmp_path)
    _runner(repo, '{"status":"ok"}')
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    original = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/fake/claude" if name == "claude" else original(name),
    )
    (repo / ".harness/harness.lock").write_text(
        '{"capabilities":["engineering-suite"]}'
    )
    return repo


def test_health_reports_preflight_readiness_without_claiming_a_live_hook(
    project: Path,
) -> None:
    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert result.id == "hooks.test_author"
    assert result.status == "ok"
    assert "preflight: ok" in result.message
    assert "external" in result.message
    assert "live" in result.message
    assert "runtime=claude" in result.message
    assert "model=configured-model" in result.message


def test_health_never_executes_a_hook_before_exact_workspace_trust(
    project: Path, tmp_path: Path
) -> None:
    (tmp_path / ".claude.json").write_text('{"projects":{}}')
    sentinel = project / "executed"
    (project / ".claude/hooks/test-author-preflight.sh").write_text(
        f'#!/bin/sh\ntouch "{sentinel}"\n'
    )

    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert result.status == "warn"
    assert "project_untrusted" in result.message
    assert not sentinel.exists()


@pytest.mark.parametrize(
    "field,reason",
    [("test_paths", "test_paths_missing"), ("test_runner", "test_runner_missing")],
)
def test_health_explains_missing_opt_in(project: Path, field: str, reason: str) -> None:
    path = project / ".harness/project.json"
    config = json.loads(path.read_text())
    config.pop(field)
    path.write_text(json.dumps(config))

    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert result.status == "skipped"
    assert reason in result.message


@pytest.mark.parametrize(
    "answer,reason",
    [
        (
            '{"status":"unavailable","reason":"isolation_unavailable","detail":"private-token"}',
            "isolation_unavailable",
        ),
        ("not-json private-token", "preflight_failed"),
    ],
)
def test_health_preserves_a_sanitized_refusal(
    project: Path, answer: str, reason: str
) -> None:
    _runner(project, answer)
    if reason == "preflight_failed":
        (project / ".claude/hooks/test-author-preflight.sh").write_text(
            "#!/bin/sh\nprintf 'not-json private-token\\n'\n"
        )

    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert result.status == "warn"
    assert reason in result.message
    assert "private-token" not in result.message


def test_health_json_contains_the_registered_activation_check(project: Path) -> None:
    report = to_json(registry.run(project))

    entry = next(row for row in report["checks"] if row["id"] == "hooks.test_author")
    assert entry["status"] == "ok"


def test_health_reports_the_configured_runtime_without_running_another_adapter(
    project: Path,
) -> None:
    path = project / ".harness/project.json"
    config = json.loads(path.read_text())
    config["test_author"] = {
        "runtime": "codex",
        "model": "configured-codex-model",
        "effort": "high",
    }
    path.write_text(json.dumps(config))
    sentinel = project / "wrong-adapter"
    (project / ".claude/hooks/test-author-preflight.sh").write_text(
        f'#!/bin/sh\ntouch "{sentinel}"\n'
    )

    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert "runtime=codex" in result.message
    assert "model=configured-codex-model" in result.message
    assert "runtime_unsupported" in result.message
    assert result.status == "warn"
    assert not sentinel.exists()


def test_health_names_the_supported_runtime_and_where_to_select_it(
    project: Path,
) -> None:
    path = project / ".harness/project.json"
    config = json.loads(path.read_text())
    config["test_author"] = {"runtime": "codex", "model": "m", "effort": "high"}
    path.write_text(json.dumps(config))

    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert "runtime_unsupported" in result.message
    assert "поддержан runtime: claude" in result.message
    assert "assignment_plans.developer.runtimes" in result.message
    assert "assignment_plans.developer.default_runtime" in result.message


def test_health_scopes_preflight_to_the_main_checkout_and_names_in_process_tdd(
    project: Path,
) -> None:
    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert "preflight: ok (основной checkout)" in result.message
    assert "in-process developer в worker worktree — обычный TDD" in result.message
