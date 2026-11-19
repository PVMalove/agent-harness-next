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
        assert (
            "SessionStart" not in json.loads((tmp_path / filename).read_text())["hooks"]
        )


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
