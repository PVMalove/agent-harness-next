"""Catalog trust is a project setting, with independent catalog and payload pins."""

import hashlib
import json
from pathlib import Path

from tests.core.test_uninstall import git, harness


def test_catalog_discovery_and_pinned_preset_install_are_separate(
    tmp_path: Path,
) -> None:
    git(tmp_path, "init", "-b", "main")
    assert (
        harness("init", str(tmp_path), "--capability", "engineering-suite").returncode
        == 0
    )
    directory = tmp_path / "team-packs"
    directory.mkdir()
    preset = directory / "payments.json"
    preset.write_text(json.dumps({"id": "payments", "project": {"language": "en"}}))
    index = directory / "index.json"
    index.write_text(
        json.dumps(
            {
                "presets": [
                    {
                        "id": "payments",
                        "description": "Payments checklist",
                        "file": "payments.json",
                        "sha256": hashlib.sha256(preset.read_bytes()).hexdigest(),
                    }
                ]
            }
        )
    )
    registry = tmp_path / ".harness/catalogs.json"
    source = {
        "id": "team",
        "index": "team-packs/index.json",
        "access": "discovery-only",
    }
    registry.write_text(json.dumps({"sources": [source]}))

    listing = harness("catalogs", str(tmp_path))
    assert listing.returncode == 0, listing.stderr
    result = json.loads(listing.stdout)["catalogs"][0]
    assert result["access"] == "discovery-only"
    assert result["presets"][0]["id"] == "payments"

    command = (
        "presets",
        str(tmp_path),
        "--catalog",
        "team",
        "--entry",
        "payments",
        "--apply",
    )
    assert "discovery-only" in harness(*command).stderr
    source.update(
        {
            "access": "install-allowed",
            "sha256": hashlib.sha256(index.read_bytes()).hexdigest(),
        }
    )
    registry.write_text(json.dumps({"sources": [source]}))
    original = preset.read_bytes()
    preset.write_bytes(original + b" ")
    assert "preset SHA-256 mismatch" in harness(*command).stderr

    preset.write_bytes(original)
    updated = harness(*command)
    assert updated.returncode == 0, updated.stderr
    assert (
        json.loads((tmp_path / ".harness/project.json").read_bytes())["language"]
        == "en"
    )
    index.write_bytes(index.read_bytes() + b" ")
    assert "catalog SHA-256 mismatch" in harness(*command).stderr
