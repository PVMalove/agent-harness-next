"""Installed workflow overlays extend named checks without rewriting base commands."""

import json
from pathlib import Path

from harness.orchestration.core.config import _config
from tests.core.test_uninstall import git, harness


def test_workflow_overlays_apply_precedence_and_preserve_base_gate(
    tmp_path: Path,
) -> None:
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
    (tmp_path / ".harness/orchestration.json").write_text(
        json.dumps({"verification_commands": ["base-gate"]})
    )
    manifest = tmp_path / "overlays.json"
    manifest.write_text(
        json.dumps(
            {
                "overlays": [
                    {
                        "id": "project",
                        "priority": 1,
                        "edits": [
                            {
                                "slot": "pre-qa",
                                "operation": "replace",
                                "commands": ["check-contract"],
                            },
                            {
                                "slot": "post-developer",
                                "operation": "append",
                                "commands": ["lint-diff"],
                            },
                        ],
                    },
                    {
                        "id": "team",
                        "priority": 10,
                        "edits": [
                            {
                                "slot": "pre-qa",
                                "operation": "append",
                                "commands": ["team-check"],
                            },
                        ],
                    },
                ]
            }
        )
    )

    result = harness(
        "workflow-overlays", str(tmp_path), "--manifest", str(manifest), "--apply"
    )

    assert result.returncode == 0, result.stderr
    slots = json.loads(result.stdout)["slots"]
    assert slots["pre-qa"] == ["check-contract"]
    effective = _config(tmp_path)
    assert effective["verification_commands"] == ["check-contract", "base-gate"]
    assert effective["developer_verification_commands"] == ["base-gate", "lint-diff"]

    data = json.loads(manifest.read_bytes())
    data["overlays"][0]["edits"][0]["slot"] = "publish"
    manifest.write_text(json.dumps(data))
    before = (tmp_path / ".harness/orchestration.json").read_bytes()
    refused = harness(
        "workflow-overlays", str(tmp_path), "--manifest", str(manifest), "--apply"
    )
    assert refused.returncode != 0
    assert (tmp_path / ".harness/orchestration.json").read_bytes() == before
