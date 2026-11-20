"""Minimal configuration bytes for console unit tests, without UI startup."""

import json
import shutil
from pathlib import Path

from harness.configuration_schema import PACKAGE


def installed_project(repo: Path) -> bytes:
    root = repo / ".harness"
    root.mkdir()
    (root / "project.schema.json").write_bytes(
        (PACKAGE / "project/project.schema.json").read_bytes()
    )
    raw = json.dumps(
        {
            "language": "ru",
            "base_branch": "main",
            "branch_pattern": "^feature/issue-[0-9]+-.+",
            "qa_gate_commands": ["pytest"],
            "tracker": {"type": "local"},
        }
    ).encode()
    (root / "project.json").write_bytes(raw)
    return raw


def _orchestration_project(repo: Path) -> None:
    from harness.configuration_schema import PACKAGE

    installed_project(repo)
    root = repo / ".harness/orchestration"
    shutil.copytree(PACKAGE / "orchestration/roles", root / "roles")
    (root / "orchestration.schema.json").write_bytes(
        (PACKAGE / "orchestration/orchestration.schema.json").read_bytes()
    )
    (repo / ".harness/orchestration.json").write_bytes(
        (PACKAGE / "orchestration.example.json").read_bytes()
    )
