"""Installed skill provenance through the public harness CLI."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from harness.json_types import JsonObject

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


def test_inventory_includes_hook_and_template_provenance(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    assert (
        harness("init", str(tmp_path), "--capability", "engineering-suite").returncode
        == 0
    )
    hook = tmp_path / ".claude/hooks/check-branch-name.sh"
    hook.write_bytes(hook.read_bytes() + b"\n# local\n")
    user_hook = hook.with_name("local.sh")
    user_hook.write_text("#!/bin/sh\n")
    template = tmp_path / "docs/agents/git-workflow.md"
    template.unlink()

    result = harness("inventory", str(tmp_path), "--json")

    assert result.returncode == 0, result.stderr
    inventory = json.loads(result.stdout)
    hooks = {item["path"]: item for item in inventory["hooks"]}
    templates = {item["path"]: item for item in inventory["templates"]}
    assert hooks[".claude/hooks/check-branch-name.sh"] == {
        "path": ".claude/hooks/check-branch-name.sh",
        "package_source": "harness/project/hooks/check-branch-name.sh",
        "status": "modified",
    }
    assert hooks[".claude/hooks/local.sh"]["status"] == "project"
    assert (
        hooks[".codex/hooks.json"]["package_source"]
        == "harness/project/codex-hooks.json.tmpl"
    )
    assert templates["docs/agents/git-workflow.md"] == {
        "path": "docs/agents/git-workflow.md",
        "package_source": "harness/project/instructions/git-workflow.md",
        "status": "missing",
    }


def test_mcp_reads_commit_map_without_creating_project_cache(tmp_path: Path) -> None:
    import io

    from harness.mcp_server import serve

    git(tmp_path, "init", "-b", "main")
    (tmp_path / "design.md").write_text("# Design\n")
    git(tmp_path, "add", "design.md")
    git(
        tmp_path,
        "-c",
        "user.name=Tester",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "design",
    )
    sha = git(tmp_path, "rev-parse", "HEAD")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "repo_map", "arguments": {"commit": sha}},
    }
    result = io.BytesIO()

    serve(
        tmp_path, lambda _: {}, io.BytesIO(json.dumps(request).encode() + b"\n"), result
    )

    payload = json.loads(result.getvalue())["result"]["structuredContent"]
    assert payload["commit"] == sha
    assert [item["path"] for item in payload["files"]] == ["design.md"]
    assert not (tmp_path / ".harness").exists()


def test_inventory_reports_runtime_discovery_and_project_skills(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    installed = harness("init", str(tmp_path), "--capability", "engineering-suite")
    assert installed.returncode == 0, installed.stderr
    (tmp_path / ".claude/skills").unlink()
    local = tmp_path / ".harness/skills/local-policy/SKILL.md"
    local.parent.mkdir()
    local.write_text("# Local policy\n")

    result = harness("inventory", str(tmp_path), "--json")
    text = harness("inventory", str(tmp_path))

    assert result.returncode == 0, result.stderr
    discovery = {item["path"]: item for item in json.loads(result.stdout)["discovery"]}
    assert discovery[".claude/skills"] == {
        "path": ".claude/skills",
        "target": "../.harness/skills",
        "runtimes": ["claude"],
        "status": "missing",
    }
    assert discovery[".agents/skills"]["status"] == "linked"
    assert ".claude/skills -> ../.harness/skills  claude  [missing]" in text.stdout
    assert ".harness/skills/local-policy/SKILL.md  project  [project]" in text.stdout


def _mcp_call(
    repo: Path,
    name: str,
    arguments: dict[str, str],
    inventory: Callable[[Path], JsonObject],
) -> JsonObject:
    import io

    from harness.mcp_server import serve

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    sink = io.BytesIO()
    serve(repo, inventory, io.BytesIO(json.dumps(request).encode() + b"\n"), sink)
    answer: JsonObject = json.loads(sink.getvalue())
    return answer


def test_mcp_qa_without_orchestration_is_not_retryable(tmp_path: Path) -> None:
    git(tmp_path, "init", "-b", "main")
    arguments = {"ticket": "#1", "branch": "feature/x", "candidate_commit": "a" * 40}

    answer = _mcp_call(tmp_path, "accepted_qa", arguments, lambda _: {})

    assert answer["result"]["isError"] is True
    assert answer["result"]["structuredContent"]["error"] == {
        "code": "orchestration_not_installed",
        "retryable": False,
    }


def test_mcp_oversized_answer_names_the_narrowing_of_its_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness import mcp_server

    monkeypatch.setattr(mcp_server, "MAX_FRAME", 400)
    inventory = {
        "schema_version": 1,
        "discovery": [],
        "skills": [{"name": "x" * 500}],
        "hooks": [],
        "templates": [],
    }

    skills = _mcp_call(tmp_path, "skill_inventory", {}, lambda _: inventory)
    artifacts = _mcp_call(tmp_path, "artifact_inventory", {}, lambda _: inventory)

    assert skills["error"]["message"].endswith("Filter the inventory by skill name.")
    assert artifacts["error"]["message"].endswith("Filter the inventory by kind.")
