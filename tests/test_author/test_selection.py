"""Author execution follows the selected developer, or explicit short-route project settings."""

import pytest
import json
import subprocess
import shutil
from pathlib import Path

from harness.health import test_author as author
from harness.health.test_author import AuthorUnavailable, read_author, select_author


def test_full_route_inherits_the_actual_developer_instead_of_project_settings() -> None:
    project = {
        "test_author": {"runtime": "claude", "model": "project-model", "effort": "low"}
    }
    brief = {
        "role": "developer",
        "resolved_runtime": "codex",
        "resolved_model": "selected-developer-model",
        "resolved_effort": "high",
    }

    assert select_author(project, developer=brief) == {
        "runtime": "codex",
        "model": "selected-developer-model",
        "effort": "high",
        "source": "developer",
    }


def test_short_route_uses_only_the_explicit_project_executor() -> None:
    project = {
        "test_author": {
            "runtime": "custom",
            "model": "project-model",
            "effort": "medium",
        }
    }

    assert select_author(project) == {
        "runtime": "custom",
        "model": "project-model",
        "effort": "medium",
        "source": "project",
    }


def test_missing_short_route_settings_never_default_to_a_provider() -> None:
    with pytest.raises(AuthorUnavailable, match="test_author_missing"):
        select_author({})


@pytest.mark.parametrize(
    "profile",
    [
        None,
        {},
        {"runtime": "claude", "model": "m"},
        {"runtime": "claude", "model": "bad model", "effort": "high"},
        {"runtime": "claude", "model": "m", "effort": "invented"},
        {"runtime": "codex", "model": "m", "effort": "high", "extra": True},
    ],
)
def test_invalid_short_route_settings_fail_instead_of_choosing_another_executor(
    profile: object,
) -> None:
    with pytest.raises(AuthorUnavailable, match="test_author_config_invalid"):
        select_author({"test_author": profile})


def test_an_incomplete_developer_brief_never_falls_back_to_project() -> None:
    project = {
        "test_author": {"runtime": "claude", "model": "project", "effort": "low"}
    }
    with pytest.raises(AuthorUnavailable, match="test_author_config_invalid"):
        select_author(project, developer={"role": "developer"})


def test_health_uses_the_planned_developer_profile_without_overriding_a_live_brief(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".harness"
    root.mkdir()
    (root / "project.json").write_text(
        json.dumps(
            {"test_author": {"runtime": "claude", "model": "short", "effort": "low"}}
        )
    )
    (root / "orchestration.json").write_text(
        json.dumps(
            {
                "assignment_plans": {
                    "developer": {
                        "default_runtime": "codex",
                        "runtimes": {
                            "codex": {"model": "planned", "effort": "high"},
                            "claude": {"model": "other", "effort": "low"},
                        },
                    }
                }
            }
        )
    )
    brief = tmp_path / "brief.json"
    brief.write_text(
        json.dumps(
            {
                "role": "developer",
                "resolved_runtime": "claude",
                "resolved_model": "actual",
                "resolved_effort": "medium",
            }
        )
    )

    assert read_author(tmp_path, planned=True) == {
        "runtime": "codex",
        "model": "planned",
        "effort": "high",
        "source": "orchestration.developer (planned)",
    }
    assert read_author(tmp_path, brief=brief, planned=True) == {
        "runtime": "claude",
        "model": "actual",
        "effort": "medium",
        "source": "developer",
    }
    assert read_author(tmp_path) == {
        "runtime": "claude",
        "model": "short",
        "effort": "low",
        "source": "project",
    }


def test_short_launcher_sends_the_project_model_and_effort_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[list[str]] = []

    def execute(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if "--worktree" in command:
            return subprocess.CompletedProcess(command, 0, '{"status":"ok"}', "")
        sent.append(command)
        assert kwargs["input"] == "one behavioral requirement"
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(shutil, "which", lambda name: f"/tools/{name}")
    monkeypatch.setattr(author, "execute", execute)
    profile = select_author(
        {
            "test_author": {
                "runtime": "claude",
                "model": "chosen-project-model",
                "effort": "high",
            }
        }
    )

    assert author.run_author(tmp_path, profile, "one behavioral requirement") == 0
    assert sent[0][sent[0].index("--model") + 1] == "chosen-project-model"
    assert sent[0][sent[0].index("--effort") + 1] == "high"
    assert "haiku" not in sent[0]


def test_unsupported_selected_runtime_starts_no_other_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never_run(*args: object, **kwargs: object) -> None:
        pytest.fail("An unsupported runtime must not execute another provider")

    monkeypatch.setattr(author, "execute", never_run)
    profile = select_author(
        {"test_author": {"runtime": "codex", "model": "selected", "effort": "high"}}
    )

    with pytest.raises(AuthorUnavailable, match="runtime_unsupported"):
        author.run_author(tmp_path, profile, "requirement")
