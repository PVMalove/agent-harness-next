"""Project runtime events produce native configs and preserve user ownership."""

import json
from pathlib import Path

from tests.core.test_uninstall import git, harness


def test_events_sync_to_three_runtimes_and_remove_only_owned_entries(
    tmp_path: Path,
) -> None:
    git(tmp_path, "init", "-b", "main")
    manifest = tmp_path / ".harness/runtime-events.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "runtimes": ["claude", "codex", "cursor"],
                "events": {"session_start": ["python scripts/session.py"]},
            }
        )
    )
    cursor = tmp_path / ".cursor/hooks.json"
    cursor.parent.mkdir()
    own = {"version": 1, "hooks": {"sessionStart": [{"command": "echo own"}]}}
    cursor.write_text(json.dumps(own))

    result = harness("runtime-events", str(tmp_path))

    assert result.returncode == 0, result.stderr
    nested = [{"hooks": [{"type": "command", "command": "python scripts/session.py"}]}]
    for filename in (".claude/settings.json", ".codex/hooks.json"):
        assert (
            json.loads((tmp_path / filename).read_text())["hooks"]["SessionStart"]
            == nested
        )
    assert json.loads(cursor.read_text())["hooks"]["sessionStart"] == [
        {"command": "echo own"},
        {"command": "python scripts/session.py"},
    ]

    manifest.unlink()
    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert json.loads(cursor.read_text()) == own
    for filename in (".claude/settings.json", ".codex/hooks.json"):
        assert not (tmp_path / filename).exists()


def test_explicit_skill_invocation_survives_update(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    install = harness(
        "init",
        str(tmp_path),
        "--capability",
        "engineering-suite",
        "--no-model-invocation",
        "grilling",
    )
    assert install.returncode == 0, install.stderr

    update = harness("update", str(tmp_path))
    assert update.returncode == 0, update.stderr
    skill = tmp_path / ".harness/skills/grilling"
    assert "disable-model-invocation: true" in (skill / "SKILL.md").read_text()
    assert (
        "allow_implicit_invocation: false" in (skill / "agents/openai.yaml").read_text()
    )
    assert harness("diff", str(tmp_path), "--json").returncode == 0

    cleared = harness(
        "update", str(tmp_path), "--clear-no-model-invocation", "grilling"
    )
    assert cleared.returncode == 0, cleared.stderr
    assert "disable-model-invocation:" not in (skill / "SKILL.md").read_text()
    publish = tmp_path / ".harness/skills/to-pull-requests"
    assert "disable-model-invocation: true" in (publish / "SKILL.md").read_text()


def test_event_ownership_preserves_a_locally_edited_native_handler(
    tmp_path: Path,
) -> None:
    git(tmp_path, "init", "-b", "main")
    manifest = tmp_path / ".harness/runtime-events.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "runtimes": ["cursor"],
                "events": {"stop": ["python scripts/artifact.py"]},
            }
        )
    )
    assert harness("runtime-events", str(tmp_path)).returncode == 0
    path = tmp_path / ".cursor/hooks.json"
    config = json.loads(path.read_text())
    config["hooks"]["stop"][0]["timeout"] = 5
    path.write_text(json.dumps(config))

    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert json.loads(path.read_text()) == config
    manifest.unlink()
    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert json.loads(path.read_text()) == config


def test_explicit_invocation_preserves_unmanaged_codex_metadata(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    assert (
        harness("init", str(tmp_path), "--capability", "engineering-suite").returncode
        == 0
    )
    skill = tmp_path / ".harness/skills/qa-gate"
    metadata = skill / "agents/openai.yaml"
    metadata.parent.mkdir(exist_ok=True)
    local = b'interface:\n  display_name: "Local QA"\n'
    metadata.write_bytes(local)
    before = (skill / "SKILL.md").read_bytes()

    result = harness("update", str(tmp_path), "--no-model-invocation", "qa-gate")

    assert result.returncode == 1
    assert "unmanaged Codex skill metadata" in result.stderr
    assert metadata.read_bytes() == local
    assert (skill / "SKILL.md").read_bytes() == before


def test_clearing_invocation_does_not_remove_linked_metadata(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    args = ("--capability", "engineering-suite", "--no-model-invocation", "qa-gate")
    assert harness("init", str(tmp_path), *args).returncode == 0
    agents = tmp_path / ".harness/skills/qa-gate/agents"
    local = tmp_path / "local-agents"
    agents.rename(local)
    agents.symlink_to(local, target_is_directory=True)

    result = harness("update", str(tmp_path), "--clear-no-model-invocation", "qa-gate")

    assert result.returncode == 1
    assert "explicit invocation refuses linked path" in result.stderr
    assert (local / "openai.yaml").is_file()
    assert agents.is_symlink()


def _integration_problems(repo: Path) -> list[str]:
    from harness.health.project_files import validate_integrations

    problems: list[str] = []
    validate_integrations(repo, problems)
    return problems


def test_runtime_event_configs_stay_inventoried_through_update(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    installed = harness("init", str(tmp_path), "--capability", "engineering-suite")
    assert installed.returncode == 0, installed.stderr
    manifest = tmp_path / ".harness/runtime-events.json"
    manifest.write_text(
        json.dumps(
            {
                "runtimes": ["claude", "codex"],
                "events": {"session_start": ["python scripts/session.py"]},
            }
        )
    )

    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert _integration_problems(tmp_path) == []
    updated = harness("update", str(tmp_path))
    assert updated.returncode == 0, updated.stderr
    assert _integration_problems(tmp_path) == []

    manifest.unlink()
    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert _integration_problems(tmp_path) == []
    inventory = json.loads((tmp_path / ".harness/integrations.json").read_text())
    assert not [
        entry
        for entry in inventory["integrations"]
        if entry["id"].startswith("runtime-events-")
    ]


def test_uninstall_removes_only_harness_runtime_event_entries(tmp_path: Path) -> None:
    from harness.uninstall import CONFIRM_WORD, apply_uninstall, plan_uninstall

    git(tmp_path, "init", "-b", "main")
    installed = harness("init", str(tmp_path), "--capability", "engineering-suite")
    assert installed.returncode == 0, installed.stderr
    settings = tmp_path / ".claude/settings.json"
    own = {
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "echo own"}]}]
        },
    }
    settings.write_text(json.dumps(own))
    (tmp_path / ".harness/runtime-events.json").write_text(
        json.dumps({"runtimes": ["claude"], "events": {"stop": ["python stop.py"]}})
    )
    assert harness("runtime-events", str(tmp_path)).returncode == 0
    assert json.loads(settings.read_text()) != own

    plan = plan_uninstall(tmp_path)
    result = apply_uninstall(tmp_path, plan, confirm=CONFIRM_WORD)

    assert result["failed"] == []
    assert json.loads(settings.read_text()) == own
    assert not (tmp_path / ".harness").exists()
