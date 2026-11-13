"""Behavior tests for the fail-closed test-author preflight."""

from __future__ import annotations

import json
import os
import stat
import sys
import subprocess
from pathlib import Path
from typing import cast

import pytest

from tests.conftest import find_bash

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = ROOT / "harness" / "project" / "hooks" / "test-author-preflight.sh"
GUARD = ROOT / "harness" / "project" / "hooks" / "test-author-guard.py"
AGENT = ROOT / "harness" / "project" / "agents" / "test-author.md"


def _project(
    tmp_path: Path, *, test_paths: object = ["tests/**"], name: str = "project"
) -> Path:
    """Create a trusted project with a controllable isolation probe."""
    project = tmp_path / name
    _install(project, test_paths=test_paths)
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"projects": {str(project.resolve()): {"hasTrustDialogAccepted": True}}}
        ),
        encoding="utf-8",
    )
    return project


def _install(project: Path, *, test_paths: object = ["tests/**"]) -> None:
    """Install the preflight, its guard, agent and selector into one checkout."""
    (project / ".harness").mkdir(parents=True, exist_ok=True)
    hooks = project / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (project / ".claude" / "agents").mkdir()
    (project / "tests").mkdir(exist_ok=True)
    (project / "src").mkdir(exist_ok=True)
    config = {
        "language": "en",
        "base_branch": "main",
        "branch_pattern": "^feature/.+",
        "qa_gate_commands": [],
        "test_paths": test_paths,
        "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
        "test_author": {
            "runtime": "claude",
            "model": "configured-model",
            "effort": "high",
        },
    }
    (project / ".harness" / "project.json").write_text(
        json.dumps(config), encoding="utf-8"
    )
    for source, target in (
        (GUARD, hooks / "test-author-guard.py"),
        (PREFLIGHT, hooks / "test-author-preflight.sh"),
    ):
        target.write_bytes(source.read_bytes())
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
    (project / ".claude" / "agents" / "test-author.md").write_bytes(AGENT.read_bytes())
    health = project / ".harness/health"
    health.mkdir()
    (health / "test_author.py").write_bytes(
        (ROOT / "harness/health/test_author.py").read_bytes()
    )
    for name in ("configuration.py", "json_types.py"):
        (project / ".harness" / name).write_bytes(
            (ROOT / "harness" / name).read_bytes()
        )


def _linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A trusted main checkout and an installed linked worktree outside it, with no trust entry."""
    main = _project(tmp_path, name="main")
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=main,
        check=True,
    )
    worker = tmp_path / "worker"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "feature/issue-1-worker", str(worker)],
        cwd=main,
        check=True,
    )
    _install(worker)
    _runner(worker, '{"status":"ok"}')
    return main, worker


def _runner(project: Path, answer: str) -> None:
    """Install a runner stub with the probe answer used by the preflight seam."""
    path = project / ".claude" / "hooks" / "run-test.sh"
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{answer}'\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _run(
    project: Path,
    *,
    env_overrides: dict[str, str | None] | None = None,
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Run preflight and keep its machine-readable output bounded."""
    environment = dict(
        os.environ,
        CLAUDE_PROJECT_DIR=str(project),
        HOME=str(project.parent),
        USERPROFILE=str(project.parent),
    )
    environment.pop("CLAUDE_CONFIG_DIR", None)
    for key, value in (env_overrides or {}).items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value
    return subprocess.run(
        [
            find_bash(),
            str(project / ".claude" / "hooks" / "test-author-preflight.sh"),
            *args,
        ],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


def _answer(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Assert the preflight process contract and parse its only output line."""
    assert result.returncode == 0
    assert result.stderr == ""
    assert len(result.stdout.splitlines()) == 1
    return cast(dict[str, object], json.loads(result.stdout))


def test_preflight_activates_only_after_probe_and_scoped_hook_contract_passes(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')

    answer = _answer(_run(project))

    assert answer == {"status": "ok"}


def test_full_route_uses_the_approved_developer_instead_of_short_route_profile(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    brief = tmp_path / "developer.json"
    brief.write_text(
        json.dumps(
            {
                "role": "developer",
                "resolved_runtime": "codex",
                "resolved_model": "developer-model",
                "resolved_effort": "high",
            }
        )
    )

    assert _answer(_run(project, args=("--brief", str(brief)))) == {
        "status": "disabled",
        "reason": "runtime_unsupported",
    }

    data = json.loads(brief.read_text())
    data["resolved_runtime"] = "claude"
    brief.write_text(json.dumps(data))
    project_config = project / ".harness/project.json"
    config = json.loads(project_config.read_text())
    config["test_author"]["runtime"] = "codex"
    project_config.write_text(json.dumps(config))
    assert _answer(_run(project, args=("--brief", str(brief)))) == {"status": "ok"}
    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "runtime_unsupported",
    }


def test_preflight_takes_the_project_root_from_git_without_claude_project_dir(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')

    for value in (None, ""):
        overrides: dict[str, str | None] = {"CLAUDE_PROJECT_DIR": value}
        assert _answer(_run(project, env_overrides=overrides)) == {"status": "ok"}


def test_claude_project_dir_other_than_the_git_root_is_a_project_dir_mismatch(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    other = tmp_path / "other-checkout"
    other.mkdir()
    link = tmp_path / "project-link"
    link.symlink_to(project, target_is_directory=True)

    for value in (str(other), str(tmp_path / "missing"), str(project / "src")):
        result = _run(project, env_overrides={"CLAUDE_PROJECT_DIR": value})
        assert _answer(result) == {
            "status": "disabled",
            "reason": "project_dir_mismatch",
        }
        assert value not in result.stdout
    # The comparison is canonical: a symlink to the Git root names the same project.
    assert _answer(_run(project, env_overrides={"CLAUDE_PROJECT_DIR": str(link)})) == {
        "status": "ok"
    }


def test_linked_worktree_of_a_trusted_repository_needs_no_trust_entry_of_its_own(
    tmp_path: Path,
) -> None:
    _, worker = _linked_worktree(tmp_path)
    state = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert str(worker.resolve()) not in state["projects"]

    result = _run(
        worker,
        env_overrides={"CLAUDE_PROJECT_DIR": None},
        args=("--worktree", str(worker)),
    )

    assert _answer(result) == {"status": "ok"}


def test_linked_worktree_of_an_untrusted_repository_stays_untrusted(
    tmp_path: Path,
) -> None:
    main, worker = _linked_worktree(tmp_path)
    (tmp_path / ".claude.json").write_text(
        json.dumps(_trust_state(main, {"hasTrustDialogAccepted": False})),
        encoding="utf-8",
    )

    assert _answer(_run(worker)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }


def test_directory_pointing_into_a_trusted_repository_is_not_its_worktree(
    tmp_path: Path,
) -> None:
    main, worker = _linked_worktree(tmp_path)
    # An unregistered directory borrows the worker's Git metadata: Git resolves the trusted
    # repository for it, but that repository does not list it as one of its worktrees.
    stranger = tmp_path / "stranger"
    stranger.mkdir()
    (stranger / ".git").write_bytes((worker / ".git").read_bytes())
    _install(stranger)
    _runner(stranger, '{"status":"ok"}')
    resolved = subprocess.run(
        ["git", "rev-parse", "--show-toplevel", "--git-common-dir"],
        cwd=stranger,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert Path(resolved[0]).resolve() == stranger.resolve()
    assert (stranger / resolved[1]).resolve() == (main / ".git").resolve()

    assert _answer(_run(stranger)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }


def test_preflight_fails_closed_without_claude_workspace_trust(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    state = tmp_path / ".claude.json"
    data = json.loads(state.read_text(encoding="utf-8"))
    data["projects"][str(project.resolve())]["hasTrustDialogAccepted"] = False
    state.write_text(json.dumps(data), encoding="utf-8")

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }


def test_preflight_requires_the_installed_test_author_agent(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / ".claude" / "agents" / "test-author.md").unlink()
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "agent_missing",
    }


def test_preflight_requires_an_enabled_scoped_hook(tmp_path: Path) -> None:
    project = _project(tmp_path)
    agent = project / ".claude" / "agents" / "test-author.md"
    agent.write_text(
        agent.read_text(encoding="utf-8").replace(
            "  PreToolUse:\n", "  PreToolUse: {}\n"
        ),
        encoding="utf-8",
    )
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "scoped_hook_unsupported",
    }


@pytest.mark.parametrize("variable", ["CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SAFE_MODE"])
def test_preflight_disables_unsupported_claude_code_modes(
    tmp_path: Path, variable: str
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project, env_overrides={variable: "1"})) == {
        "status": "disabled",
        "reason": "claude_code_unsupported",
    }


def test_missing_test_paths_disables_test_author(tmp_path: Path) -> None:
    project = _project(tmp_path, test_paths=None)
    data = json.loads((project / ".harness" / "project.json").read_text())
    data.pop("test_paths")
    (project / ".harness" / "project.json").write_text(json.dumps(data))
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "test_paths_missing",
    }


def test_unavailable_isolation_disables_test_author_without_detail_leak(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(
        project,
        '{"status":"unavailable","reason":"isolation_unavailable","detail":"bwrap_missing"}',
    )

    answer = _answer(_run(project))

    assert answer == {"status": "disabled", "reason": "isolation_unavailable"}


def test_runner_configuration_is_required_for_activation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    data = json.loads((project / ".harness" / "project.json").read_text())
    data.pop("test_runner")
    (project / ".harness" / "project.json").write_text(json.dumps(data))
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "test_runner_missing",
    }


@pytest.mark.parametrize("bad_answer", ["not-json", '{"status":"disabled"}'])
def test_unverifiable_guard_or_probe_fails_closed(
    tmp_path: Path, bad_answer: str
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    if bad_answer == "not-json":
        (project / ".claude" / "hooks" / "test-author-guard.py").write_text(
            "print('not-json')\n", encoding="utf-8"
        )
    else:
        (project / ".claude" / "hooks" / "run-test.sh").write_text(
            "#!/bin/sh\nprintf '%s\\n' '{\"status\":\"disabled\"}'\n",
            encoding="utf-8",
        )
        (project / ".claude" / "hooks" / "run-test.sh").chmod(
            (project / ".claude" / "hooks" / "run-test.sh").stat().st_mode
            | stat.S_IXUSR
        )

    answer = _answer(_run(project))

    expected = (
        "guard_hook_unavailable"
        if bad_answer == "not-json"
        else "isolation_unavailable"
    )
    assert answer == {"status": "disabled", "reason": expected}


def _trust_state(project: Path, entry: object) -> dict[str, object]:
    """A `.claude.json` body with one project entry."""
    return {"projects": {str(project.resolve()): entry}}


@pytest.mark.parametrize(
    "state",
    [
        "missing-file",
        "invalid-json",
        "not-an-object",
        "projects-not-an-object",
        "other-project-only",
        "entry-not-an-object",
        "trust-is-a-string",
        "trust-not-accepted",
        "entry-without-trust",
    ],
)
def test_every_unverifiable_trust_state_fails_closed(
    tmp_path: Path, state: str
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    path = tmp_path / ".claude.json"
    bodies: dict[str, object] = {
        "invalid-json": "{not json",
        "not-an-object": "[]",
        "projects-not-an-object": json.dumps({"projects": []}),
        "other-project-only": json.dumps(
            {"projects": {"/elsewhere": {"hasTrustDialogAccepted": True}}}
        ),
        "entry-not-an-object": json.dumps(_trust_state(project, True)),
        "trust-is-a-string": json.dumps(
            _trust_state(project, {"hasTrustDialogAccepted": "true"})
        ),
        "trust-not-accepted": json.dumps(
            _trust_state(project, {"hasTrustDialogAccepted": False})
        ),
        "entry-without-trust": json.dumps(_trust_state(project, {})),
    }
    if state == "missing-file":
        path.unlink()
    else:
        path.write_text(str(bodies[state]), encoding="utf-8")

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }


def test_claude_config_dir_overrides_the_default_trust_file(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    overrides: dict[str, str | None] = {"CLAUDE_CONFIG_DIR": str(config_dir)}

    # The default file trusts the project, but the configured directory has no decision.
    assert _answer(_run(project, env_overrides=overrides)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }

    (config_dir / ".claude.json").write_text(
        json.dumps(_trust_state(project, {"hasTrustDialogAccepted": True})),
        encoding="utf-8",
    )
    assert _answer(_run(project, env_overrides=overrides)) == {"status": "ok"}


def test_project_path_with_a_space_still_activates(tmp_path: Path) -> None:
    project = _project(tmp_path, name="my project")
    _runner(project, '{"status":"ok"}')

    assert _answer(_run(project)) == {"status": "ok"}


def test_unknown_reasons_from_guard_or_probe_are_not_passed_through(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(
        project,
        '{"status":"unavailable","reason":"secret detail","detail":"/home/user"}',
    )
    probe = _answer(_run(project))

    guard = project / ".claude" / "hooks" / "test-author-guard.py"
    guard.write_text(
        "import json\nprint(json.dumps({'status': 'disabled', 'reason': 'leak /home/user'}))\n",
        encoding="utf-8",
    )
    _runner(project, '{"status":"ok"}')
    config = _answer(_run(project))

    assert probe == {"status": "disabled", "reason": "isolation_unavailable"}
    assert config == {"status": "disabled", "reason": "guard_hook_unavailable"}


def test_trust_given_only_to_a_parent_directory_keeps_the_author_disabled(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"projects": {str(tmp_path.resolve()): {"hasTrustDialogAccepted": True}}}
        ),
        encoding="utf-8",
    )

    # Claude Code may trust the project through its parent, but without an entry for the exact
    # path the preflight stays on the safe side (docs/agents/test-author.md, section 3).
    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "project_untrusted",
    }


@pytest.mark.parametrize("reason", ["config_invalid", "write_zone_rejected"])
def test_preflight_preserves_runner_mount_refusal(tmp_path: Path, reason: str) -> None:
    project = _project(tmp_path)
    _runner(
        project, json.dumps({"status": "unavailable", "reason": reason, "detail": None})
    )
    assert _answer(_run(project)) == {"status": "disabled", "reason": reason}


_MISMATCH = {"status": "disabled", "reason": "checkout_mismatch"}


def test_worktree_argument_naming_the_served_checkout_keeps_the_zero_argument_answer(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    link = tmp_path / "project-link"
    link.symlink_to(project, target_is_directory=True)

    assert _answer(_run(project, args=("--worktree", str(project)))) == {"status": "ok"}
    # The comparison is canonical: a symlink to the served checkout is the same checkout.
    assert _answer(_run(project, args=("--worktree", str(link)))) == {"status": "ok"}


def test_worktree_argument_naming_another_checkout_is_a_checkout_mismatch(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    worker = tmp_path / "worker-checkout"
    worker.mkdir()

    result = _run(project, args=("--worktree", str(worker)))

    assert _answer(result) == _MISMATCH
    assert str(worker) not in result.stdout


@pytest.mark.parametrize(
    "args",
    [
        ("--worktree", "missing-directory"),
        ("--worktree", ""),
        ("--worktree",),
        ("--worktree", "{project}", "extra"),
        ("--unknown", "{project}"),
        ("{project}",),
    ],
)
def test_unresolvable_or_unknown_arguments_are_a_checkout_mismatch(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    argv = tuple(item.replace("{project}", str(project)) for item in args)

    assert _answer(_run(project, args=argv)) == _MISMATCH


@pytest.mark.parametrize(
    "override",
    ["model: haiku", "model: inherit\neffort: low", "model: inherit\nmodel: sonnet"],
)
def test_preflight_refuses_stale_or_overridden_author_settings(
    tmp_path: Path, override: str
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    agent = project / ".claude/agents/test-author.md"
    agent.write_text(agent.read_text().replace("model: inherit", override))

    assert _answer(_run(project)) == {
        "status": "disabled",
        "reason": "test_author_config_invalid",
    }


@pytest.mark.skipif(os.name == "nt", reason="native CLI fixture is a POSIX executable")
def test_portable_short_launcher_applies_project_settings_in_a_fresh_process(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    _runner(project, '{"status":"ok"}')
    (project / ".harness/storage.py").write_bytes(
        (ROOT / "harness/storage.py").read_bytes()
    )
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    binary = binary_dir / "claude"
    binary.write_text(
        f"#!{sys.executable}\nimport json, pathlib, sys\npathlib.Path('selected.json').write_text(json.dumps(sys.argv[1:]))\nassert sys.stdin.read() == 'one requirement'\n"
    )
    binary.chmod(0o755)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("one requirement")
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "CLAUDE_CONFIG_DIR": str(tmp_path),
        "PATH": str(binary_dir) + os.pathsep + os.environ["PATH"],
    }
    command = [
        sys.executable,
        "-I",
        "-B",
        str(project / ".harness/health/test_author.py"),
        "run",
        "--repo",
        str(project),
        "--prompt-file",
        str(prompt),
    ]
    result = subprocess.run(
        command, cwd=project, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    argv = json.loads((project / "selected.json").read_text())
    assert argv[argv.index("--model") + 1] == "configured-model"
    assert argv[argv.index("--effort") + 1] == "high"
    assert "--agent" in argv

    config_path = project / ".harness/project.json"
    config = json.loads(config_path.read_text())
    config["test_author"]["runtime"] = "codex"
    config_path.write_text(json.dumps(config))
    (project / "selected.json").unlink()
    result = subprocess.run(
        command, cwd=project, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 3
    assert json.loads(result.stdout) == {
        "status": "disabled",
        "reason": "runtime_unsupported",
    }
    assert not (project / "selected.json").exists()


@pytest.mark.skipif(
    os.name == "nt", reason="protected adapter fixture uses a POSIX shell"
)
def test_full_generic_preflight_preserves_the_native_parent_checkout_identity(
    tmp_path: Path,
) -> None:
    worker = _project(tmp_path)
    _runner(worker, '{"status":"ok"}')
    brief = tmp_path / "developer.json"
    brief.write_text(
        json.dumps(
            {
                "role": "developer",
                "resolved_runtime": "claude",
                "resolved_model": "developer-model",
                "resolved_effort": "high",
            }
        )
    )
    command = [
        sys.executable,
        "-I",
        "-B",
        str(worker / ".harness/health/test_author.py"),
        "preflight",
        "--repo",
        str(worker),
        "--brief",
        str(brief),
    ]
    env = {
        **os.environ,
        "CLAUDE_CONFIG_DIR": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }
    result = subprocess.run(
        command, cwd=worker, env=env, capture_output=True, text=True, check=False
    )
    assert _answer(result) == {"status": "disabled", "reason": "project_dir_mismatch"}
    env["CLAUDE_PROJECT_DIR"] = str(worker)
    result = subprocess.run(
        command, cwd=worker, env=env, capture_output=True, text=True, check=False
    )
    assert _answer(result) == {"status": "ok"}
    # A native parent that did not pass its identity is checked by the Git root alone.
    del env["CLAUDE_PROJECT_DIR"]
    result = subprocess.run(
        command, cwd=worker, env=env, capture_output=True, text=True, check=False
    )
    assert _answer(result) == {"status": "ok"}


@pytest.mark.skipif(os.name == "nt", reason="native CLI fixture is a POSIX executable")
def test_in_process_developer_launches_the_author_bound_to_its_worktree(
    tmp_path: Path,
) -> None:
    main, worker = _linked_worktree(tmp_path)
    (worker / ".harness/storage.py").write_bytes(
        (ROOT / "harness/storage.py").read_bytes()
    )
    brief = tmp_path / "developer.json"
    brief.write_text(
        json.dumps(
            {
                "role": "developer",
                "resolved_runtime": "claude",
                "resolved_model": "developer-model",
                "resolved_effort": "high",
            }
        )
    )
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    binary = binary_dir / "claude"
    binary.write_text(
        f"#!{sys.executable}\nimport json, os, pathlib, sys\n"
        "pathlib.Path('launched.json').write_text(json.dumps("
        "{'argv': sys.argv[1:], 'project': os.environ.get('CLAUDE_PROJECT_DIR')}))\n"
    )
    binary.chmod(0o755)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("one requirement")
    # An in-process developer is a subagent of the main checkout's session.
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(main),
        "PATH": str(binary_dir) + os.pathsep + os.environ["PATH"],
    }
    env.pop("CLAUDE_CONFIG_DIR", None)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(worker / ".harness/health/test_author.py"),
            "run",
            "--repo",
            str(worker),
            "--brief",
            str(brief),
            "--prompt-file",
            str(prompt),
        ],
        cwd=main,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (main / "launched.json").exists()
    launched = json.loads((worker / "launched.json").read_text())
    assert launched["project"] == str(worker.resolve())
    argv = launched["argv"]
    assert argv[argv.index("--agent") + 1] == "test-author"
    assert argv[argv.index("--model") + 1] == "developer-model"
