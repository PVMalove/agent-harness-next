"""Installed skill provenance through the public harness CLI."""

import json
from pathlib import Path

from tests.core.test_uninstall import git, harness


def test_inventory_resolves_managed_source_and_local_edits(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    installed = harness("init", str(tmp_path), "--capability", "engineering-suite")
    assert installed.returncode == 0, installed.stderr
    grilling = tmp_path / ".harness/skills/grilling/SKILL.md"
    grilling.write_bytes(grilling.read_bytes() + b"\nLocal note.\n")
    local = tmp_path / ".harness/skills/local-policy/SKILL.md"
    local.parent.mkdir()
    local.write_text("# Local policy\n")

    result = harness("inventory", str(tmp_path), "--json")

    assert result.returncode == 0, result.stderr
    inventory = json.loads(result.stdout)
    assert inventory["schema_version"] == 1
    by_name = {skill["name"]: skill for skill in inventory["skills"]}
    assert by_name["grilling"] == {
        "name": "grilling",
        "path": ".harness/skills/grilling/SKILL.md",
        "package_source": "skills/first-party/engineering/grilling/SKILL.md",
        "capabilities": ["engineering-suite"],
        "drift": {"local_changed": [".harness/skills/grilling/SKILL.md"]},
    }
    assert by_name["local-policy"]["package_source"] is None
    assert by_name["local-policy"]["capabilities"] == []


def test_mcp_serves_inventory_and_refuses_unknown_tools(tmp_path: Path) -> None:
    import subprocess
    import sys

    from tests.core.test_uninstall import CLI

    git(tmp_path, "init", "-b", "main")
    assert (
        harness("init", str(tmp_path), "--capability", "engineering-suite").returncode
        == 0
    )
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "skill_inventory",
                "arguments": {"name": "grilling"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_command",
                "arguments": {"command": "touch modified"},
            },
        },
    ]
    args = [sys.executable, str(CLI), "mcp", str(tmp_path)]
    result = subprocess.run(
        args,
        input="\n".join(map(json.dumps, requests)) + "\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    init, inventory, refused = map(json.loads, result.stdout.splitlines())
    assert init["result"]["protocolVersion"] == "2025-11-25"
    assert inventory["result"]["structuredContent"]["skills"][0]["name"] == "grilling"
    assert refused["error"]["code"] == -32602
    assert not (tmp_path / "modified").exists()
