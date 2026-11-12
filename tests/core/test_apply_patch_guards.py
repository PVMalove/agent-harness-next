"""Критичные guards Write/Edit на payload `apply_patch` второго runtime (issue #830).

Каждый hook запускается через точку входа с JSON на stdin. Вердикт для патча сравнивается с
вердиктом эквивалентного Write первого runtime; патч на несколько файлов блокируется, если
заблокирован хоть один его путь.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.orchestration.hook_policy import parse_hook_response

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "harness" / "project" / "hooks"
AGENT = ROOT / "harness" / "project" / "agents" / "test-author.md"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="the hooks are bash scripts")

POLICY = {"profile": "standard"}
CONFIG: dict[str, object] = {
    "language": "en",
    "base_branch": "master",
    "branch_pattern": "^feature/issue-[0-9]+-.+",
    "qa_gate_commands": ["true"],
    "test_paths": ["tests/**"],
    "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
    "hook_policy": POLICY,
}


def _config_text(document: dict[str, object]) -> str:
    return json.dumps(document, indent=2) + "\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".harness").mkdir(parents=True)
    (root / "docs" / "tasks").mkdir(parents=True)
    (root / ".claude" / "agents").mkdir(parents=True)
    (root / ".codex").mkdir()
    (root / "tests").mkdir()
    (root / "src").mkdir()
    shutil.copytree(
        HOOKS, root / ".claude" / "hooks", ignore=shutil.ignore_patterns("__pycache__")
    )
    (root / ".claude" / "agents" / "test-author.md").write_bytes(AGENT.read_bytes())
    (root / ".harness" / "project.json").write_text(
        _config_text(CONFIG), encoding="utf-8"
    )
    (root / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
    (root / "docs" / "note.md").write_text("old\n", encoding="utf-8")
    return root


def _patch(*sections: str) -> str:
    return "*** Begin Patch\n" + "".join(sections) + "*** End Patch\n"


def _add(path: str, text: str = "x") -> str:
    return f"*** Add File: {path}\n+{text}\n"


def _hook(
    project: Path, hook_id: str, payload: dict[str, object], *, first_runtime: bool
) -> tuple[int, str, str]:
    """Run the installed hook: the first runtime sets CLAUDE_PROJECT_DIR, the second only cds."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("CLAUDE_PROJECT_DIR", "HARNESS_HOOK_ENVELOPE")
    }
    if first_runtime:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    done = subprocess.run(
        [str(BASH), str(project / ".claude" / "hooks" / f"{hook_id}.sh")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=project,
        check=False,
        timeout=60,
    )
    verdict = parse_hook_response(done.stderr)
    return done.returncode, str(verdict["decision"]), str(verdict["reason_code"])


def _apply_patch(
    project: Path, hook_id: str, patch: str, cwd: Path | None = None
) -> tuple[int, str, str]:
    payload: dict[str, object] = {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "tool_name": "apply_patch",
        "cwd": str(cwd or project),
        "tool_input": {"command": patch},
    }
    return _hook(project, hook_id, payload, first_runtime=False)


def _write(
    project: Path, hook_id: str, path: str, content: str = "x"
) -> tuple[int, str, str]:
    payload: dict[str, object] = {
        "session_id": "s1",
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(project),
        "tool_input": {"file_path": str(project / path), "content": content},
    }
    return _hook(project, hook_id, payload, first_runtime=True)


BLOCK_CONFIG = (2, "block", "agent-config-edit")
BLOCK_POLICY = (2, "block", "hook-policy-changed")
BLOCK_SCRATCH = (2, "block", "scratch-location")
ALLOW = (0, "allow", "ok")


def test_a_patch_to_the_second_runtime_hooks_file_is_blocked_like_a_write(
    project: Path,
) -> None:
    patch = _patch(
        '*** Update File: .codex/hooks.json\n@@\n-{"hooks": {}}\n+{"hooks": {"x": 1}}\n'
    )

    assert _apply_patch(project, "protect-hook-policy", patch) == BLOCK_CONFIG
    assert _write(project, "protect-hook-policy", ".codex/hooks.json") == BLOCK_CONFIG


def test_a_relative_path_resolves_against_the_payload_cwd(project: Path) -> None:
    patch = _patch(_add("settings.local.json", "{}"))

    assert (
        _apply_patch(project, "protect-hook-policy", patch, cwd=project / ".claude")
        == BLOCK_CONFIG
    )
    assert (
        _write(project, "protect-hook-policy", ".claude/settings.local.json")
        == BLOCK_CONFIG
    )


def test_an_absolute_path_is_kept(project: Path) -> None:
    patch = _patch(_add(str(project / ".claude" / "hooks" / "evil.sh")))

    assert (
        _apply_patch(project, "protect-hook-policy", patch, cwd=project / "docs")
        == BLOCK_CONFIG
    )


def test_a_multi_file_patch_is_blocked_when_one_path_is_blocked(project: Path) -> None:
    patch = _patch(
        _add("docs/tasks/ok.md"),
        "*** Update File: docs/note.md\n@@\n-old\n+new\n",
        "*** Delete File: .codex/hooks.json\n",
    )

    assert _apply_patch(project, "protect-hook-policy", patch) == BLOCK_CONFIG
    assert _write(project, "protect-hook-policy", "docs/tasks/ok.md") == ALLOW


def test_hook_policy_edits_decide_like_the_equivalent_write(project: Path) -> None:
    other = _config_text({**CONFIG, "language": "ru"})
    changed = _config_text({**CONFIG, "hook_policy": {"profile": "minimal"}})
    other_key = _patch(
        '*** Update File: .harness/project.json\n@@\n-  "language": "en",\n'
        '+  "language": "ru",\n'
    )
    policy_key = _patch(
        '*** Update File: .harness/project.json\n@@\n-    "profile": "standard"\n'
        '+    "profile": "minimal"\n'
    )

    assert _apply_patch(project, "protect-hook-policy", other_key) == ALLOW
    assert (
        _write(project, "protect-hook-policy", ".harness/project.json", other) == ALLOW
    )
    assert _apply_patch(project, "protect-hook-policy", policy_key) == BLOCK_POLICY
    assert (
        _write(project, "protect-hook-policy", ".harness/project.json", changed)
        == BLOCK_POLICY
    )


def test_deleting_or_moving_project_json_decides_by_its_hook_policy(
    project: Path,
) -> None:
    delete = _patch("*** Delete File: .harness/project.json\n")
    away = _patch(
        "*** Update File: .harness/project.json\n*** Move to: docs/old.json\n"
        '@@\n-  "language": "en",\n+  "language": "en",\n'
    )
    (project / "docs" / "policy-free.json").write_text('{"a": 1}\n', encoding="utf-8")
    onto = _patch(
        "*** Update File: docs/policy-free.json\n*** Move to: .harness/project.json\n"
        '@@\n-{"a": 1}\n+{"a": 2}\n'
    )

    assert _apply_patch(project, "protect-hook-policy", delete) == BLOCK_POLICY
    assert _apply_patch(project, "protect-hook-policy", away) == BLOCK_POLICY
    assert _apply_patch(project, "protect-hook-policy", onto) == BLOCK_POLICY


def test_an_unappliable_update_of_project_json_is_refused(project: Path) -> None:
    patch = _patch("*** Update File: .harness/project.json\n@@\n-absent\n+x\n")

    assert _apply_patch(project, "protect-hook-policy", patch) == (
        2,
        "block",
        "hook-policy-unparseable",
    )


def test_a_shell_apply_patch_into_the_hooks_config_is_blocked(project: Path) -> None:
    command = (
        "cd .codex && apply_patch <<'EOF'\n"
        + _patch('*** Update File: hooks.json\n@@\n-{"hooks": {}}\n+{}\n')
        + "EOF"
    )
    payload: dict[str, object] = {
        "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {"command": command},
    }
    loose: dict[str, object] = {
        "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {"command": "echo start; " + command},
    }
    harmless: dict[str, object] = {
        "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {
            "command": "apply_patch <<'EOF'\n" + _patch(_add("docs/tasks/a.md")) + "EOF"
        },
    }

    for runtime in (True, False):
        assert _hook(
            project, "protect-hook-policy", payload, first_runtime=runtime
        ) == (BLOCK_CONFIG)
        assert _hook(project, "protect-hook-policy", loose, first_runtime=runtime) == (
            BLOCK_CONFIG
        )
        assert _hook(
            project, "protect-hook-policy", harmless, first_runtime=runtime
        ) == (ALLOW)


def test_first_runtime_write_and_edit_decisions_are_unchanged(project: Path) -> None:
    edit: dict[str, object] = {
        "tool_name": "Edit",
        "cwd": str(project),
        "tool_input": {
            "file_path": str(project / ".harness" / "project.json"),
            "old_string": '"standard"',
            "new_string": '"minimal"',
        },
    }

    assert (
        _write(project, "protect-hook-policy", ".claude/settings.json") == BLOCK_CONFIG
    )
    assert _write(project, "protect-hook-policy", "docs/a.md") == ALLOW
    assert (
        _hook(project, "protect-hook-policy", edit, first_runtime=True) == BLOCK_POLICY
    )
    assert _write(project, "block-scratch-outside-docs-tasks", "docs/pr-body-1.md") == (
        BLOCK_SCRATCH
    )
    assert (
        _write(project, "block-scratch-outside-docs-tasks", "docs/tasks/a.md") == ALLOW
    )


@pytest.mark.parametrize(
    ("patch", "cwd", "write_path", "expected"),
    [
        (
            _patch(_add("docs/tasks/pr-body-1.md")),
            "",
            "docs/tasks/pr-body-1.md",
            BLOCK_SCRATCH,
        ),
        (_patch(_add("../outside.md")), "", "../outside.md", BLOCK_SCRATCH),
        (_patch(_add("docs/tasks/note.md")), "", "docs/tasks/note.md", ALLOW),
        (
            _patch(_add("pr-body-2.md")),
            "docs/tasks",
            "docs/tasks/pr-body-2.md",
            BLOCK_SCRATCH,
        ),
        (_patch(_add("note.md")), "docs/tasks", "docs/tasks/note.md", ALLOW),
        (
            _patch(
                _add("docs/tasks/ok.md"), _add(".harness/.sandboxes/pr_body/notes.md")
            ),
            "",
            ".harness/.sandboxes/pr_body/notes.md",
            BLOCK_SCRATCH,
        ),
        (
            _patch(
                "*** Update File: docs/note.md\n*** Move to: docs/tasks/issue-comment-1.md\n"
                "@@\n-old\n+new\n"
            ),
            "",
            "docs/tasks/issue-comment-1.md",
            BLOCK_SCRATCH,
        ),
        (_patch(), "", "docs/tasks/note.md", ALLOW),
    ],
)
def test_the_scratch_guard_decides_each_patch_path_like_a_write(
    project: Path,
    patch: str,
    cwd: str,
    write_path: str,
    expected: tuple[int, str, str],
) -> None:
    hook = "block-scratch-outside-docs-tasks"

    assert _apply_patch(project, hook, patch, cwd=project / cwd) == expected
    assert _write(project, hook, write_path) == expected


def _author(project: Path, tool: str, tool_input: dict[str, object], cwd: Path) -> str:
    payload: dict[str, object] = {
        "agent_type": "test-author",
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "cwd": str(cwd),
        "tool_input": tool_input,
    }
    done = subprocess.run(
        [sys.executable, str(project / ".claude" / "hooks" / "test-author-guard.py")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        cwd=project,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    if not done.stdout:
        return "allow"
    return str(
        json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    )


@pytest.mark.parametrize(
    ("patch", "cwd", "write_path", "expected"),
    [
        (_patch(_add("tests/test_a.py")), "", "tests/test_a.py", "allow"),
        (_patch(_add("test_b.py")), "tests", "tests/test_b.py", "allow"),
        (
            _patch(_add("src/a.py")),
            "",
            "src/a.py",
            "test-author: write_outside_test_paths",
        ),
        (
            _patch(_add("tests/test_a.py"), "*** Delete File: src/a.py\n"),
            "",
            "src/a.py",
            "test-author: write_outside_test_paths",
        ),
        (
            _patch(
                "*** Update File: tests/test_a.py\n*** Move to: src/a.py\n@@\n-x\n+y\n"
            ),
            "",
            "src/a.py",
            "test-author: write_outside_test_paths",
        ),
        (
            _patch(_add(".claude/hooks/run-test.sh")),
            "",
            ".claude/hooks/run-test.sh",
            "test-author: write_outside_test_paths",
        ),
        (_patch(), "", "tests/test_a.py", "allow"),
    ],
)
def test_the_test_author_guard_decides_each_patch_path_like_a_write(
    project: Path, patch: str, cwd: str, write_path: str, expected: str
) -> None:
    assert (
        _author(project, "apply_patch", {"command": patch}, project / cwd) == expected
    )
    assert (
        _author(project, "Write", {"file_path": write_path, "content": "x"}, project)
        == expected
    )


UNPARSEABLE = (2, "block", "apply-patch-unparseable")
BROKEN_PATCHES = [
    "*** Add File: a.md\n+x\n",
    "*** Begin Patch\n*** Add File: \n+x\n*** End Patch",
    "*** Begin Patch\n*** Update File: docs/note.md\n*** End Patch",
    "*** Begin Patch\n*** Add File: docs/tasks/a.md\n+x\n*** End Patch\nrm -rf /",
]


def _remedy(project: Path, hook_id: str, tool_input: dict[str, object]) -> str:
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(project),
        "tool_input": tool_input,
    }
    env = {
        key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"
    }
    done = subprocess.run(
        [str(BASH), str(project / ".claude" / "hooks" / f"{hook_id}.sh")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=project,
        check=False,
        timeout=60,
    )
    verdict = parse_hook_response(done.stderr)
    assert (done.returncode, verdict["decision"], verdict["reason_code"]) == UNPARSEABLE
    return str(verdict["remedy"])


@pytest.mark.parametrize(
    "hook_id", ["protect-hook-policy", "block-scratch-outside-docs-tasks"]
)
@pytest.mark.parametrize("patch", BROKEN_PATCHES)
def test_an_unparsable_patch_blocks_every_critical_guard_with_a_remedy(
    project: Path, hook_id: str, patch: str
) -> None:
    remedy = _remedy(project, hook_id, {"command": patch})

    assert "*** Begin Patch" in remedy and "*** Add File:" in remedy, remedy
    assert "rm -rf" not in remedy


@pytest.mark.parametrize(
    "hook_id", ["protect-hook-policy", "block-scratch-outside-docs-tasks"]
)
@pytest.mark.parametrize(
    "tool_input", [{}, {"command": ["*** Begin Patch"]}, {"command": 7}]
)
def test_a_patch_payload_without_a_string_command_blocks_fail_closed(
    project: Path, hook_id: str, tool_input: dict[str, object]
) -> None:
    assert "*** Begin Patch" in _remedy(project, hook_id, tool_input)


def test_a_shell_apply_patch_the_runtime_would_reject_blocks(project: Path) -> None:
    command = "apply_patch <<'EOF'\n*** Begin Patch\n*** Update File: docs/note.md\nEOF"
    payload: dict[str, object] = {
        "tool_name": "Bash",
        "cwd": str(project),
        "tool_input": {"command": command},
    }

    assert (
        _hook(project, "protect-hook-policy", payload, first_runtime=True)
        == UNPARSEABLE
    )


@pytest.mark.parametrize("patch", BROKEN_PATCHES)
def test_the_test_author_guard_refuses_an_unparsable_patch_with_a_remedy(
    project: Path, patch: str
) -> None:
    reason = _author(project, "apply_patch", {"command": patch}, project)

    assert reason.startswith("test-author: patch_unparseable: "), reason
    assert "*** Begin Patch" in reason and "rm -rf" not in reason
