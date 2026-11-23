"""Codex proposes one test-file edit; the harness applies and runs it in isolation."""

from __future__ import annotations

from collections.abc import Mapping
from difflib import unified_diff
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from harness.health import isolated_runner

LIMIT = 128 * 1024
TEST_FILE = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+")
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {key: {"type": "string"} for key in ("path", "before", "after", "test_id")},
    "required": ["path", "before", "after", "test_id"],
    "additionalProperties": False,
}


class CodexRefused(Exception):
    """A fixed refusal reason safe to return to the developer."""


def preflight(repo: Path, brief: Mapping[str, object] | None) -> None:
    if shutil.which("codex") is None:
        raise CodexRefused("runtime_unavailable")
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repo, capture_output=True, text=True, timeout=10, check=False,
    )
    if root.returncode or Path(root.stdout.strip()).resolve() != repo:
        raise CodexRefused("checkout_mismatch")
    if brief is not None:
        worktree = brief.get("worktree")
        tools = brief.get("allowed_tools")
        if not isinstance(worktree, str) or Path(worktree).resolve() != repo:
            raise CodexRefused("checkout_mismatch")
        approval = brief.get("coordinator_approval")
        if not isinstance(approval, dict) or not all(
            isinstance(approval.get(field), str) and approval[field].strip()
            for field in ("approved_by", "approved_at")
        ):
            raise CodexRefused("test_author_config_invalid")
        if brief.get("access") != "write" or not isinstance(tools, list) or not (
            "Agent(test-author)" in tools or "Agent" in tools
        ):
            raise CodexRefused("agent_tool_unavailable")
    problem = isolated_runner.probe(repo, readonly_tests=True)
    if problem is not None:
        raise CodexRefused("isolation_unavailable")


def _command(
    binary: str, selection: Mapping[str, object], schema: Path, response: Path
) -> list[str]:
    return [
        binary, "--ask-for-approval", "never", "exec",
        "--strict-config", "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check",
        "--disable", "shell_tool", "--disable", "hooks", "--disable", "multi_agent",
        "--disable", "apps", "--disable", "plugins",
        "-c", 'web_search="disabled"', "-c", "mcp_servers={}",
        "-c", 'default_permissions="test-author"',
        "-c", 'permissions.test-author.filesystem={":minimal"="read",":workspace_roots"="read"}',
        "-c", 'shell_environment_policy.inherit="none"',
        "--model", str(selection["model"]),
        "-c", f'model_reasoning_effort="{selection["effort"]}"',
        "--output-schema", str(schema),
        "--output-last-message", str(response),
        "-",
    ]


def _patch(repo: Path, response: object, brief: Mapping[str, object] | None) -> tuple[str, str]:
    if not isinstance(response, dict) or set(response) != {"path", "before", "after", "test_id"}:
        raise CodexRefused("test_proposal_invalid")
    name, before, after, test_id = (response[key] for key in ("path", "before", "after", "test_id"))
    if not all(isinstance(value, str) for value in (name, before, after, test_id)):
        raise CodexRefused("test_proposal_invalid")
    if not TEST_FILE.fullmatch(name) or {".", ".."}.intersection(name.split("/")):
        raise CodexRefused("write_outside_test_paths")
    if not isolated_runner.valid_test_id(test_id) or not test_id.startswith(name + "::"):
        raise CodexRefused("test_id_invalid")
    path = repo / name
    settings = isolated_runner.load_settings(repo)
    zones = isolated_runner.write_zones(repo, settings.test_paths)
    if not any(zone in path.parents for zone in zones) or path.resolve() != path:
        raise CodexRefused("write_outside_test_paths")
    if brief is not None:
        from harness.orchestration.contract import paths_inside, string_list

        paths = brief.get("write_paths")
        allowed = brief.get("allowed_paths")
        if not string_list(paths) or not paths_inside([name], paths):
            raise CodexRefused("write_outside_test_paths")
        if allowed is not None and (
            not string_list(allowed) or not paths_inside([name], allowed)
        ):
            raise CodexRefused("write_outside_test_paths")
    if not after.endswith("\n") or (before and not before.endswith("\n")) or before == after:
        raise CodexRefused("test_proposal_invalid")
    exists = path.exists()
    actual = path.read_bytes() if exists and path.is_file() and path.stat().st_size <= LIMIT else None
    if (exists and actual != before.encode("utf-8")) or (not exists and before):
        raise CodexRefused("test_proposal_stale")
    patch = "".join(
        unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{name}" if exists else "/dev/null",
            tofile=f"b/{name}",
            n=len(before.splitlines()),
        )
    )
    return patch, test_id


def run(
    repo: Path,
    binary: str,
    selection: Mapping[str, object],
    prompt: str,
    *,
    brief: Mapping[str, object] | None,
) -> int:
    # Keep the scratch outside a project-local TMPDIR; Windows has no /tmp.
    scratch_root = None if os.name == "nt" else "/tmp"
    with tempfile.TemporaryDirectory(prefix="harness-codex-author-", dir=scratch_root) as directory:
        scratch = Path(directory)
        schema = scratch / "schema.json"
        response = scratch / "answer.json"
        schema.write_text(json.dumps(RESPONSE_SCHEMA), encoding="utf-8")
        result = subprocess.run(
            _command(binary, selection, schema, response),
            input=(
                "Write one behavioral test using only the context below. "
                "Return the repository-relative test path, its complete original text "
                "(empty for a new file), the complete updated text, and one pytest node ID. "
                "Use a final newline in the updated text.\n\n" + prompt
            ),
            cwd=scratch, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=240, check=False,
        )
        if result.returncode or not response.is_file() or response.is_symlink():
            raise CodexRefused("author_unavailable")
        with response.open("rb") as stream:
            data = stream.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise CodexRefused("test_proposal_invalid")
        try:
            answer = json.loads(data)
        except (ValueError, RecursionError):
            raise CodexRefused("test_proposal_invalid") from None
    patch, test_id = _patch(repo, answer, brief)
    applied = subprocess.run(
        ["git", "apply", "--no-index", "-"], input=patch,
        cwd=repo, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=10, check=False,
    )
    if applied.returncode:
        raise CodexRefused("test_proposal_stale")
    outcome = isolated_runner.run_test(repo, test_id, readonly_tests=True)
    print(isolated_runner.render(outcome))
    return 3 if outcome.result == "refused" else 0
