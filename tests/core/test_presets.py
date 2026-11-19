"""Team presets merge project settings through the public packager."""

import json
from pathlib import Path

from tests.core.test_uninstall import git, harness


def test_preset_preview_is_read_only_and_apply_is_additive(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    assert (
        harness(
            "init",
            str(tmp_path),
            "--capability",
            "backend-orchestration",
            "--qa-gate-command",
            "base-gate",
        ).returncode
        == 0
    )
    path = tmp_path / ".harness/project.json"
    original = path.read_bytes()
    preset = tmp_path / "team.json"
    preset.write_text(
        json.dumps(
            {
                "id": "team",
                "requires": ["engineering-suite"],
                "project": {
                    "language": "en",
                    "qa_gate_commands": ["contract-check"],
                    "pr_checklist": ["Record rollout order"],
                },
            }
        )
    )
    args = ("presets", str(tmp_path), "--manifest", str(preset))

    preview = harness(*args)
    assert preview.returncode == 0, preview.stderr
    assert path.read_bytes() == original

    applied = harness(*args, "--apply")
    assert applied.returncode == 0, applied.stderr
    project = json.loads(path.read_bytes())
    assert project["language"] == "en"
    assert project["qa_gate_commands"] == ["base-gate", "contract-check"]
    assert project["pr_checklist"] == ["Record rollout order"]
    assert harness(*args, "--apply").returncode == 0
    assert json.loads(path.read_bytes()) == project


def test_schema_and_validator_agree_on_pr_checklist_items(tmp_path: Path) -> None:
    from harness.configuration_schema import schema_problems
    from harness.health.project_files import validate_project_data

    git(tmp_path, "init", "-b", "main")
    installed = harness(
        "init",
        str(tmp_path),
        "--capability",
        "engineering-suite",
        "--qa-gate-command",
        "gate",
    )
    assert installed.returncode == 0, installed.stderr
    project = json.loads((tmp_path / ".harness/project.json").read_bytes())
    for item, valid in (("Record rollout order", True), ("   ", False), ("a\n", False)):
        document = {**project, "pr_checklist": [item]}
        problems: list[str] = []
        validate_project_data(document, problems)
        assert (not problems) == valid, item
        assert (not schema_problems(tmp_path, "project.json", document)) == valid, item
