"""Health resolves the configured author before probing the selected protected adapter."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from harness.health import registry
from harness.health.checks import hooks
from harness.health.context import HealthContext
from harness.health.model import CheckResult
from harness.health.report_json import to_json
from tests.test_author.test_preflight import _linked_worktree, _project, _runner

CONDITION_IDS = [
    "hooks.test_author_config",
    "hooks.test_author_root",
    "hooks.test_author_trust",
    "hooks.test_author_guard",
    "hooks.test_author_runner",
    "hooks.test_author_probe",
]


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = _project(tmp_path)
    _runner(repo, '{"status":"ok"}')
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
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


def test_health_scopes_preflight_to_this_checkout_and_names_the_in_process_launcher(
    project: Path,
) -> None:
    result = hooks.check_test_author(HealthContext(repo=project, lock={}, online=False))

    assert "preflight: ok (этот checkout)" in result.message
    assert (
        "in-process developer — launcher своего worktree "
        "(python3 -I -B <worktree>/.harness/health/test_author.py run --repo <worktree>"
    ) in result.message
    assert "обычный TDD" not in result.message


def _context(repo: Path) -> HealthContext:
    return HealthContext(repo=repo, lock={}, online=False)


def _condition(repo: Path, check_id: str) -> CheckResult:
    check = dict(registry.REGISTRY)[check_id]
    return check(_context(repo))


def _without_project_author(repo: Path) -> None:
    path = repo / ".harness/project.json"
    config = json.loads(path.read_text())
    config.pop("test_author")
    path.write_text(json.dumps(config))


def _developer_plan(repo: Path) -> None:
    (repo / ".harness/orchestration.json").write_text(
        json.dumps(
            {
                "assignment_plans": {
                    "developer": {
                        "runtimes": {
                            "claude": {
                                "model": "plan-model",
                                "effort": "medium",
                                "transport": "in-process",
                            }
                        }
                    }
                }
            }
        )
    )


def test_health_prints_a_separate_line_for_each_test_author_condition(
    project: Path,
) -> None:
    report = registry.run(project)

    ids = [check.id for check in report.checks]
    start = ids.index("hooks.test_author") + 1
    assert ids[start : start + len(CONDITION_IDS)] == CONDITION_IDS
    statuses = {check.id: check.status for check in report.checks}
    assert {
        check_id: statuses[check_id] for check_id in CONDITION_IDS
    } == dict.fromkeys(CONDITION_IDS, "ok")


def test_missing_test_author_block_prints_the_block_from_the_developer_plan(
    project: Path,
) -> None:
    _without_project_author(project)
    _developer_plan(project)

    result = _condition(project, "hooks.test_author_config")

    assert result.status == "warn"
    assert "test_author_missing" in result.message
    assert result.fix is not None
    assert (
        '"test_author": {"runtime": "claude", "model": "plan-model", "effort": "medium"}'
        in result.fix.text
    )
    assert result.fix.command is not None and "health" in result.fix.command
    assert "--fix" in result.fix.command


def test_missing_test_author_block_without_a_developer_plan_names_the_fields(
    project: Path,
) -> None:
    _without_project_author(project)

    result = _condition(project, "hooks.test_author_config")

    assert result.status == "warn"
    assert result.fix is not None
    assert (
        '"test_author": {"runtime": "claude", "model": "<модель>", "effort": "<усилие>"}'
        in result.fix.text
    )
    assert result.fix.command is None


def test_health_fix_adds_the_test_author_block_from_the_developer_plan(
    project: Path,
) -> None:
    _without_project_author(project)
    _developer_plan(project)
    path = project / ".harness/project.json"
    before = json.loads(path.read_text())

    report = registry.run(project, fix=True)

    after = json.loads(path.read_text())
    assert after == {
        **before,
        "test_author": {"runtime": "claude", "model": "plan-model", "effort": "medium"},
    }
    assert any("test_author" in applied for applied in report.fixes_applied)
    config = next(c for c in report.checks if c.id == "hooks.test_author_config")
    assert config.status == "ok"


def test_health_fix_never_overwrites_an_existing_test_author_block(
    project: Path,
) -> None:
    _developer_plan(project)
    path = project / ".harness/project.json"
    config = json.loads(path.read_text())
    config["test_author"] = {"runtime": "claude"}
    path.write_text(json.dumps(config))
    before = path.read_bytes()

    report = registry.run(project, fix=True)

    assert path.read_bytes() == before
    assert not any("test_author" in applied for applied in report.fixes_applied)
    line = next(c for c in report.checks if c.id == "hooks.test_author_config")
    assert line.status == "warn"
    assert line.fix is not None and '"model": "plan-model"' in line.fix.text


def test_health_trusts_a_linked_worktree_through_its_trusted_main_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, worker = _linked_worktree(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    original = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name: "/fake/claude" if name == "claude" else original(name),
    )

    trust = _condition(worker, "hooks.test_author_trust")
    summary = hooks.check_test_author(_context(worker))

    assert trust.status == "ok"
    assert str(main.resolve()) in trust.message
    assert summary.status == "ok", summary.message


def test_untrusted_worktree_names_the_main_checkout_and_runs_no_project_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main, worker = _linked_worktree(tmp_path)
    (tmp_path / ".claude.json").write_text('{"projects":{}}')
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    sentinel = worker / "executed"
    for name in ("run-test.sh", "test-author-guard.py"):
        (worker / ".claude/hooks" / name).write_text(f'#!/bin/sh\ntouch "{sentinel}"\n')

    trust = _condition(worker, "hooks.test_author_trust")
    guard = _condition(worker, "hooks.test_author_guard")
    probe = _condition(worker, "hooks.test_author_probe")

    assert trust.status == "warn"
    assert "project_untrusted" in trust.message
    assert trust.fix is not None
    assert trust.fix.command == f"cd {main.resolve()} && claude"
    assert guard.status == "skipped" and probe.status == "skipped"
    assert "hooks.test_author_trust" in guard.message
    assert not sentinel.exists()


def test_claude_project_dir_other_than_the_git_root_names_both_paths(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other))

    result = _condition(project, "hooks.test_author_root")

    assert result.status == "warn"
    assert "project_dir_mismatch" in result.message
    assert str(other.resolve()) in result.message
    assert str(project.resolve()) in result.message
    assert result.fix is not None and "unset CLAUDE_PROJECT_DIR" in result.fix.text


def test_a_checkout_outside_git_has_no_project_root(project: Path) -> None:
    shutil.rmtree(project / ".git")

    result = _condition(project, "hooks.test_author_root")

    assert result.status == "warn"
    assert "project_untrusted" in result.message
    assert result.fix is not None
    assert result.fix.command == f"git -C {project.resolve()} rev-parse --show-toplevel"


@pytest.mark.parametrize(
    "missing,check_id,reason",
    [
        (
            ".claude/hooks/test-author-guard.py",
            "hooks.test_author_guard",
            "guard_hook_unavailable",
        ),
        (".claude/agents/test-author.md", "hooks.test_author_guard", "agent_missing"),
        (".claude/hooks/run-test.sh", "hooks.test_author_runner", "runner_unavailable"),
    ],
)
def test_missing_protected_files_point_to_harness_update(
    project: Path, missing: str, check_id: str, reason: str
) -> None:
    (project / missing).unlink()

    result = _condition(project, check_id)

    assert result.status == "warn"
    assert reason in result.message
    assert result.fix is not None
    assert result.fix.command is not None and " update " in f"{result.fix.command} "


def test_failed_probe_prints_the_isolation_step(project: Path) -> None:
    _runner(
        project,
        '{"status":"unavailable","reason":"isolation_unavailable","detail":"bwrap_missing"}',
    )

    result = _condition(project, "hooks.test_author_probe")

    assert result.status == "warn"
    assert "isolation_unavailable (bwrap_missing)" in result.message
    assert result.fix is not None and "bubblewrap" in result.fix.text


def test_refused_preflight_points_to_the_line_with_the_step(project: Path) -> None:
    _runner(
        project,
        '{"status":"unavailable","reason":"isolation_unavailable","detail":"bwrap_missing"}',
    )

    result = hooks.check_test_author(_context(project))

    assert result.status == "warn"
    assert result.fix is not None and "hooks.test_author_probe" in result.fix.text
