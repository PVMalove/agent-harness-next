"""`harness health` reports the `hooks.policy` check of the installed project hooks."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness.health.hook_settings import (
    CODEX_SUPPORT,
    HOOK_CATALOG,
    is_wired,
    script_name,
    supported_tools,
)
from harness.json_types import JsonObject
from tests.conftest import find_bash
from tests.core.test_uninstall import git, harness

PROJECT_TEMPLATES = Path(__file__).resolve().parents[2] / "harness" / "project"

SETTINGS = ".claude/settings.local.json"
CODEX = ".codex/hooks.json"
HOOKS_DIR = ".claude/hooks"
BASH = find_bash()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-b", "main")
    result = harness("init", str(root), "--capability", "engineering-suite")
    assert result.returncode == 0, result.stderr
    return root


def check(repo: Path) -> JsonObject:
    """The `hooks.policy` entry of `harness health --json`."""
    result = harness("health", str(repo), "--json")
    report = json.loads(result.stdout)
    found: JsonObject = next(c for c in report["checks"] if c["id"] == "hooks.policy")
    return found


def load(repo: Path, relative: str) -> JsonObject:
    document: JsonObject = json.loads((repo / relative).read_text(encoding="utf-8"))
    return document


def save(repo: Path, relative: str, document: JsonObject) -> None:
    (repo / relative).write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )


def drop_script(document: JsonObject, script: str) -> None:
    for groups in document["hooks"].values():
        for group in groups:
            group["hooks"] = [h for h in group["hooks"] if script not in h["command"]]


def test_installed_project_reports_profile_source_and_wiring(repo: Path) -> None:
    result = check(repo)

    assert result["group"] == "hooks"
    assert result["status"] == "ok"
    message = result["message"]
    assert "профиль standard" in message
    assert ".harness/project.json" in message
    assert "claude: критических hooks подключено 9/9" in message
    assert "codex: критических hooks подключено 8/8" in message


@pytest.mark.skipif(shutil.which(BASH) is None, reason="the managed hook is a Bash script")
def test_health_explains_one_hook_and_reports_an_observed_denial(repo: Path) -> None:
    hook = "block-scratch-outside-docs-tasks"
    before = harness("health", str(repo), "--hook", hook, "--json")
    assert before.returncode == 0, before.stderr
    configured = json.loads(before.stdout)
    assert configured["last_observation"] is None
    assert configured["script"] == f".claude/hooks/{hook}.sh"
    assert configured["runtimes"]["codex"]["config"] == ".codex/hooks.json"
    assert configured["runtimes"]["codex"]["bindings"][0]["event"] == "PreToolUse"
    assert "apply_patch" in configured["runtimes"]["codex"]["bindings"][0]["matcher"]

    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "cwd": str(repo),
        "tool_input": {
            "file_path": str(repo / ".harness/.sandboxes/pr_body/private-notes.md"),
            "content": "private data",
        },
    }
    denied = subprocess.run(
        [BASH, str(repo / HOOKS_DIR / f"{hook}.sh")],
        input=json.dumps(payload), capture_output=True, text=True, check=False, cwd=repo,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
    )
    assert denied.returncode == 2, denied.stderr

    after = harness("health", str(repo), "--hook", hook, "--json")
    assert after.returncode == 0, after.stderr
    observed = json.loads(after.stdout)["last_observation"]
    assert observed["decision"] == "block"
    assert observed["reason_code"] == "scratch-location"
    assert observed["body_executed"] is True
    assert observed["event"] == "PreToolUse"
    assert observed["tool"] == "Write"
    assert observed["runtime"] == "claude"
    assert observed["stale"] is False
    assert "private data" not in after.stdout
    assert "private-notes.md" not in after.stdout


def run_codex_merge_hook(checkout: Path) -> subprocess.CompletedProcess[str]:
    """`block-pr-merge` as the second runtime runs it: no Claude variable, a Codex `turn_id`."""
    payload = {
        "session_id": "s",
        "turn_id": "turn-1",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "cwd": str(checkout),
        "tool_input": {"command": " ".join(("gh", "pr", "mer" + "ge", "41", "--secret-flag"))},
    }
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    return subprocess.run(
        [BASH, str(checkout / HOOKS_DIR / "block-pr-merge.sh")],
        input=json.dumps(payload), capture_output=True, text=True, check=False,
        cwd=checkout, env=env,
    )


@pytest.mark.skipif(shutil.which(BASH) is None, reason="the managed hook is a Bash script")
def test_observation_names_the_runtime_and_goes_stale_once_that_runtime_is_unwired(
    repo: Path,
) -> None:
    hook = "block-pr-merge"
    assert run_codex_merge_hook(repo).returncode == 2

    observed = json.loads(harness("health", str(repo), "--hook", hook, "--json").stdout)
    assert observed["last_observation"]["runtime"] == "codex"
    assert observed["last_observation"]["stale"] is False
    assert "secret-flag" not in json.dumps(observed)

    document = load(repo, CODEX)
    drop_script(document, f"{hook}.sh")
    save(repo, CODEX, document)

    unwired = json.loads(harness("health", str(repo), "--hook", hook, "--json").stdout)
    assert unwired["runtimes"]["codex"]["bindings"] == []
    assert unwired["runtimes"]["claude"]["bindings"]
    assert unwired["last_observation"]["runtime"] == "codex"
    assert unwired["last_observation"]["stale"] is True


@pytest.mark.skipif(shutil.which(BASH) is None, reason="the managed hook is a Bash script")
def test_observation_from_an_issue_worktree_is_visible_from_the_main_checkout(
    repo: Path, tmp_path: Path,
) -> None:
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com",
        "commit", "--allow-empty", "-m", "init")
    worktree = tmp_path / "issue-worktree"
    git(repo, "worktree", "add", "-b", "feature/issue-1-x", str(worktree))
    shutil.copytree(repo / HOOKS_DIR, worktree / HOOKS_DIR)

    assert run_codex_merge_hook(worktree).returncode == 2

    observed = json.loads(
        harness("health", str(repo), "--hook", "block-pr-merge", "--json").stdout
    )["last_observation"]
    assert observed is not None
    assert observed["decision"] == "block"
    assert not (worktree / ".harness/.sandboxes/logs/hook-observations").exists()


def test_events_the_second_runtime_lacks_are_listed_and_apply_patch_guards_are_not(
    repo: Path,
) -> None:
    result = check(repo)

    message = result["message"]
    assert "ограничение адаптера codex:" not in message
    assert "block-scratch-outside-docs-tasks" not in message
    assert (
        "protect-hook-policy (MultiEdit, NotebookEdit; вне hook: hook_policy_sha256 в brief)"
        in message
    )
    assert (
        "check-worktree-branch-name (вне hook: batch create по branch_pattern)"
        in message
    )
    assert "count-skill-usage" in message


def test_the_second_runtime_wires_change_impact_hooks_and_lacks_only_claude_tools(
    repo: Path,
) -> None:
    result = check(repo)
    message = result["message"]

    _, marker, lacking = message.partition("codex: нет события или payload: ")
    assert marker
    # Write and Edit arrive as apply_patch; only the first runtime's MultiEdit and NotebookEdit lack.
    for row in (
        "impact-first-touch (MultiEdit, NotebookEdit; вне hook: ChangeImpact-gate по ADR 0023)",
        "sensitive-path-recheck (MultiEdit, NotebookEdit; вне hook: граница strict "
        "(dispatch propose, qa run, publish))",
        "targeted-check-reminder (MultiEdit, NotebookEdit; вне hook: сверка checks_run)",
    ):
        assert row in lacking
    for hook_id in (
        "impact-first-touch",
        "sensitive-path-recheck",
        "targeted-check-reminder",
    ):
        assert f"не подключён hook {hook_id}" not in message
    assert "claude: нет события" not in message


def test_a_missing_script_of_several_events_is_named_once(repo: Path) -> None:
    (repo / HOOKS_DIR / "targeted-check-reminder.sh").unlink()

    result = check(repo)

    assert result["status"] == "warn"
    assert result["message"].count("targeted-check-reminder.sh: файл отсутствует") == 1


def test_qa_marker_hook_is_missing_for_the_second_runtime_only(repo: Path) -> None:
    second = load(repo, CODEX)
    assert not [
        handler
        for groups in second["hooks"].values()
        for group in groups
        for handler in group["hooks"]
        if script_name(handler) == "mark-qa-gate-passed.sh"
    ]

    message = check(repo)["message"]

    assert re.search(r"codex: нет события или payload: .*mark-qa-gate-passed", message)
    assert "claude: нет события" not in message
    assert "не подключён hook mark-qa-gate-passed" not in message


def load_hook_response() -> object:
    spec = importlib.util.spec_from_file_location(
        "hook_response_catalog", PROJECT_TEMPLATES / "hooks" / "hook_response.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hook_catalog_agrees_with_the_response_envelope() -> None:
    hooks: dict[str, tuple[str, bool]] = getattr(load_hook_response(), "HOOKS")
    catalog = {spec.hook_id: spec for spec in HOOK_CATALOG}

    # `test-author-guard` is wired in the agent frontmatter and runs outside the envelope.
    assert set(catalog) - set(hooks) == {"test-author-guard"}
    assert set(hooks) <= set(catalog)
    assert {hook_id: catalog[hook_id].critical for hook_id in hooks} == {
        hook_id: critical for hook_id, (_, critical) in hooks.items()
    }
    assert catalog["test-author-guard"].critical
    for spec in HOOK_CATALOG:
        assert (PROJECT_TEMPLATES / "hooks" / spec.script).is_file(), spec.script


def test_hook_catalog_agrees_with_the_templates() -> None:
    first = json.loads((PROJECT_TEMPLATES / "settings.local.json.tmpl").read_text("utf-8"))
    second = json.loads((PROJECT_TEMPLATES / "codex-hooks.json.tmpl").read_text("utf-8"))
    agent = (PROJECT_TEMPLATES / "agents" / "test-author.md").read_text("utf-8")
    frontmatter = agent.split("---", 2)[1]

    settings_specs = [spec for spec in HOOK_CATALOG if spec.wiring == "settings"]
    wired_scripts = {
        script_name(handler)
        for groups in first["hooks"].values()
        for group in groups
        for handler in group["hooks"]
    }
    assert wired_scripts == {spec.script for spec in settings_specs}
    for spec in HOOK_CATALOG:
        if spec.wiring == "agent":
            assert spec.script in frontmatter
    for spec in settings_specs:
        for tool in spec.tools:
            assert is_wired(first, spec, tool), (spec.hook_id, tool)
            # The second runtime wires exactly what it delivers, Write/Edit via apply_patch, and
            # only the hooks shipped to it (`HookSpec.runtimes`).
            assert is_wired(second, spec, tool) == (
                tool in supported_tools(spec, CODEX_SUPPORT, "codex")
            ), (
                spec.hook_id,
                tool,
            )


def test_the_second_runtime_delivers_write_and_edit_to_patch_aware_hooks() -> None:
    catalog = {(spec.hook_id, spec.event): spec for spec in HOOK_CATALOG}

    def delivered(hook_id: str) -> tuple[str, ...]:
        return supported_tools(catalog[(hook_id, "PreToolUse")], CODEX_SUPPORT)

    assert delivered("protect-hook-policy") == ("Bash", "Write", "Edit")
    assert delivered("block-scratch-outside-docs-tasks") == ("Write", "Edit")
    assert delivered("test-author-guard") == ("Write", "Edit", "Bash")
    for advisory in (
        "impact-first-touch",
        "sensitive-path-recheck",
        "targeted-check-reminder",
    ):
        assert delivered(advisory) == ("Write", "Edit")


def test_the_runtime_autostart_hook_is_shipped_to_claude_code_only() -> None:
    specs = [spec for spec in HOOK_CATALOG if spec.hook_id == "runtime-autostart"]

    assert {(spec.event, spec.tools) for spec in specs} == {
        ("PreToolUse", ("Bash",)),
        ("Stop", ("*",)),
        ("SubagentStop", ("*",)),
    }
    for spec in specs:
        assert not spec.critical
        assert spec.runtimes == ("claude",)
        assert supported_tools(spec, CODEX_SUPPORT, "codex") == ()
        assert supported_tools(spec, CODEX_SUPPORT, "claude") == spec.tools


def test_profile_without_hook_policy_key_comes_from_the_default_source(
    repo: Path,
) -> None:
    project_json = repo / ".harness/project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    del data["hook_policy"]
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    message = check(repo)["message"]

    assert "профиль standard (по умолчанию)" in message


def test_legacy_project_keeps_the_standard_wiring_after_update(repo: Path) -> None:
    project_json = repo / ".harness/project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    del data["hook_policy"]
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    updated = harness("update", str(repo))
    assert updated.returncode == 0, updated.stderr

    result = check(repo)

    assert result["status"] == "ok"
    assert "профиль standard (по умолчанию)" in result["message"]
    assert "claude: критических hooks подключено 9/9" in result["message"]
    assert "codex: критических hooks подключено 8/8" in result["message"]
    assert "hook_policy" not in json.loads(project_json.read_text(encoding="utf-8"))


def test_escalations_are_listed_with_the_effective_profile(repo: Path) -> None:
    project_json = repo / ".harness/project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    data["hook_policy"] = {
        "profile": "standard",
        "escalations": [{"profile": "strict", "roles": ["developer"]}],
    }
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    message = check(repo)["message"]

    assert "профиль strict" in message
    assert "эскалации: strict: roles=developer" in message


def test_invalid_hook_policy_fails_because_the_hooks_apply_strict(repo: Path) -> None:
    project_json = repo / ".harness/project.json"
    data = json.loads(project_json.read_text(encoding="utf-8"))
    data["hook_policy"] = {"profile": "lenient"}
    project_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    result = check(repo)

    assert result["status"] == "fail"
    assert "применяют strict" in result["message"]


def test_missing_critical_script_fails(repo: Path) -> None:
    (repo / HOOKS_DIR / "block-dangerous-git.sh").unlink()

    result = check(repo)

    assert result["status"] == "fail"
    assert "block-dangerous-git.sh: файл отсутствует" in result["message"]


@pytest.mark.skipif(os.name == "nt", reason="the executable bit is a POSIX notion")
def test_non_executable_critical_script_fails(repo: Path) -> None:
    script = repo / HOOKS_DIR / "block-pr-merge.sh"
    script.chmod(script.stat().st_mode & ~0o111)

    result = check(repo)

    assert result["status"] == "fail"
    assert "block-pr-merge.sh: нет бита исполнения" in result["message"]


def test_removed_managed_entry_fails_and_names_the_hook(repo: Path) -> None:
    document = load(repo, SETTINGS)
    drop_script(document, "require-qa-gate.sh")
    save(repo, SETTINGS, document)

    result = check(repo)

    assert result["status"] == "fail"
    assert "claude: критических hooks подключено 8/9" in result["message"]
    assert "не подключён критический hook require-qa-gate" in result["message"]
    assert result["fix"] is not None


def test_removed_entry_of_the_second_runtime_fails(repo: Path) -> None:
    document = load(repo, CODEX)
    drop_script(document, "block-dangerous-git.sh")
    save(repo, CODEX, document)

    result = check(repo)

    assert result["status"] == "fail"
    assert (
        "не подключён критический hook block-dangerous-git (codex)" in result["message"]
    )


def test_missing_file_of_the_second_runtime_warns(repo: Path) -> None:
    (repo / CODEX).unlink()

    result = check(repo)

    assert result["status"] == "warn"
    assert ".codex/hooks.json отсутствует" in result["message"]


def test_script_drift_from_the_template_warns(repo: Path) -> None:
    script = repo / HOOKS_DIR / "count-skill-usage.sh"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# local\n", encoding="utf-8"
    )

    result = check(repo)

    assert (
        "дрейф: .claude/hooks/count-skill-usage.sh отличается от шаблона"
        in result["message"]
    )
    assert "--force-seed-file .claude/hooks/count-skill-usage.sh" in result["message"]


def test_force_seed_file_fix_says_the_file_is_backed_up(repo: Path) -> None:
    script = repo / HOOKS_DIR / "count-skill-usage.sh"
    script.write_text(
        script.read_text(encoding="utf-8") + "\n# local\n", encoding="utf-8"
    )

    fix_text = check(repo)["fix"]["text"]

    assert "--force-seed-file <путь>" in fix_text
    assert ".harness/.sandboxes/seed-backups/" in fix_text


def test_changed_managed_entry_is_reported_as_drift_not_as_a_missing_hook(
    repo: Path,
) -> None:
    document = load(repo, SETTINGS)
    for group in document["hooks"]["PreToolUse"]:
        for handler in group["hooks"]:
            if "block-dangerous-git.sh" in handler["command"]:
                handler["timeout"] = 5
    save(repo, SETTINGS, document)

    result = check(repo)

    assert result["status"] == "warn"
    assert "дрейф: конфликтов managed hooks 1 (claude)" in result["message"]
    assert "подключено 9/9" in result["message"]


def test_check_is_skipped_without_the_hooks_capabilities(tmp_path: Path) -> None:
    root = tmp_path / "plain"
    root.mkdir()
    git(root, "init", "-b", "main")
    assert harness("init", str(root)).returncode == 0

    result = check(root)

    assert result["status"] == "skipped"


def test_standalone_run_says_that_drift_was_not_checked(repo: Path) -> None:
    from harness.health import registry

    report = registry.run(repo)

    result = next(c for c in report.checks if c.id == "hooks.policy")
    assert re.search(r"дрейф не проверен", result.message)


PROJECT_JSON = ".harness/project.json"
POLICY_FILE = ".harness/hook-policy.json"
POLICY_MISSING = f"{POLICY_FILE} отсутствует"
POLICY_DRIFT = f"дрейф: {POLICY_FILE} не совпадает с effective policy"


def test_an_installed_policy_file_is_not_reported(repo: Path) -> None:
    message = check(repo)["message"]

    assert POLICY_FILE not in message


def test_a_missing_policy_file_warns_with_the_update_fix(repo: Path) -> None:
    (repo / POLICY_FILE).unlink()

    result = check(repo)

    assert result["status"] == "warn"
    assert f"{POLICY_MISSING}: effective policy hooks не записана" in result["message"]
    assert result["fix"] is not None
    assert "update" in result["fix"]["command"]


def test_a_hook_policy_change_without_update_is_drift(repo: Path) -> None:
    project = load(repo, PROJECT_JSON)
    project["hook_policy"] = {"profile": "strict"}
    save(repo, PROJECT_JSON, project)

    result = check(repo)

    assert POLICY_DRIFT in result["message"]
    assert result["status"] == "warn"


def test_a_replaced_hook_version_is_drift(repo: Path) -> None:
    document = load(repo, POLICY_FILE)
    document["hook_versions"][".claude/hooks/block-pr-merge.sh"] = "0" * 64
    save(repo, POLICY_FILE, document)

    assert POLICY_DRIFT in check(repo)["message"]


def test_an_unparsable_policy_file_is_drift(repo: Path) -> None:
    (repo / POLICY_FILE).write_text("{not json", encoding="utf-8")

    assert POLICY_DRIFT in check(repo)["message"]


def test_the_same_policy_with_crlf_line_ends_is_not_drift(repo: Path) -> None:
    path = repo / POLICY_FILE
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert POLICY_FILE not in check(repo)["message"]


def test_update_clears_the_policy_file_drift(repo: Path) -> None:
    project = load(repo, PROJECT_JSON)
    project["hook_policy"] = {"profile": "strict"}
    save(repo, PROJECT_JSON, project)
    assert POLICY_DRIFT in check(repo)["message"]

    updated = harness("update", str(repo))

    assert updated.returncode == 0, updated.stderr
    assert POLICY_FILE not in check(repo)["message"]


# A lone surrogate passes hook_policy_problems and JSON, but has no UTF-8 form: the resolver
# refuses it (PolicyError), and the hooks keep the configured profile.
UNENCODABLE_POLICY: JsonObject = {
    "profile": "minimal",
    "escalations": [{"profile": "standard", "paths": ["a\ud800b"]}],
}
UNENCODABLE_PROBLEM = (
    ".harness/project.json hook_policy text cannot be encoded as UTF-8: "
    "surrogates not allowed"
)


@pytest.mark.parametrize("policy_file", ["kept", "removed"])
def test_a_hook_policy_without_a_utf8_form_fails_with_the_resolver_problem(
    repo: Path, policy_file: str
) -> None:
    project = load(repo, PROJECT_JSON)
    project["hook_policy"] = UNENCODABLE_POLICY
    save(repo, PROJECT_JSON, project)
    if policy_file == "removed":
        (repo / POLICY_FILE).unlink()

    result = check(repo)

    message = result["message"]
    assert result["status"] == "fail"
    assert UNENCODABLE_PROBLEM in message
    assert "применяют strict" not in message
    assert "профиль standard (.harness/project.json; базовый minimal)" in message
    assert "эскалации: standard: paths=a\\ud800b" in message


def test_a_standalone_run_message_has_a_utf8_form(repo: Path) -> None:
    from harness.health import registry

    project = load(repo, PROJECT_JSON)
    project["hook_policy"] = UNENCODABLE_POLICY
    save(repo, PROJECT_JSON, project)

    report = registry.run(repo)

    result = next(c for c in report.checks if c.id == "hooks.policy")
    result.message.encode("utf-8")


def test_standalone_run_reports_a_missing_policy_file(repo: Path) -> None:
    from harness.health import registry

    (repo / POLICY_FILE).unlink()

    report = registry.run(repo)

    result = next(c for c in report.checks if c.id == "hooks.policy")
    assert POLICY_MISSING in result.message


def test_console_route_of_the_policy_warn_does_not_promise_that_update_fixes_it() -> None:
    from harness.console.kernel import i18n
    from harness.console.tui.shell import check_route

    route = check_route("hooks.policy")

    # The warn stays after `harness update` (the second runtime lacks some hooks), so the console
    # neither calls it a wiring error nor sends the user to Update Harness.
    assert route.section == "Diagnostics"
    assert "неверно" not in route.title
    assert route.title != check_route("environment.hook_bash").title
    assert i18n.tr("en", route.title) != route.title


ENVELOPE = ".claude/hooks/hook_response.py"


def forget_runtime_autostart(repo: Path) -> None:
    """An older installed envelope: its ``HOOKS`` and ``ACTIVE_PROFILES`` lack runtime-autostart."""
    envelope = repo / ENVELOPE
    text = envelope.read_text(encoding="utf-8")
    for line in (
        '    "runtime-autostart": ("runtime-autostart-failed", False),\n',
        '    "runtime-autostart": ("minimal", "standard", "strict"),\n',
    ):
        assert line in text
        text = text.replace(line, "")
    envelope.write_text(text, encoding="utf-8")


def test_a_wired_hook_the_envelope_does_not_register_fails_with_the_force_command(
    repo: Path,
) -> None:
    forget_runtime_autostart(repo)

    result = check(repo)

    assert result["status"] == "fail"
    assert "не регистрирует hook_id runtime-autostart" in result["message"]
    assert "runtime-autostart.sh, подключён" in result["message"]
    assert result["fix"]["command"].endswith(f"--force-seed-file {ENVELOPE}")
    assert ".harness/.sandboxes/seed-backups/" in result["fix"]["text"]


def test_an_unwired_hook_the_envelope_does_not_register_warns(repo: Path) -> None:
    forget_runtime_autostart(repo)
    document = load(repo, SETTINGS)
    drop_script(document, "runtime-autostart.sh")
    save(repo, SETTINGS, document)

    result = check(repo)

    assert "не регистрирует hook_id runtime-autostart (runtime-autostart.sh)" in result["message"]
    assert "подключён)" not in result["message"]
    assert result["fix"]["command"].endswith(f"--force-seed-file {ENVELOPE}")


def test_an_unreadable_envelope_hooks_table_fails(repo: Path) -> None:
    (repo / ENVELOPE).write_text("HOOKS = {\n", encoding="utf-8")

    result = check(repo)

    assert result["status"] == "fail"
    assert "hook_response.py: HOOKS не читается" in result["message"]


@pytest.mark.parametrize("envelope", [ENVELOPE, ".claude/hooks/hook-envelope.sh"])
def test_a_missing_envelope_file_fails_and_update_restores_it(
    repo: Path, envelope: str
) -> None:
    (repo / envelope).unlink()

    result = check(repo)

    assert result["status"] == "fail"
    assert f"{envelope}: файл отсутствует" in result["message"]
    assert "без JSON-конверта" in result["message"]
    assert result["fix"]["command"].endswith(f"update {repo}")
    assert harness("update", str(repo)).returncode == 0
    assert (repo / envelope).is_file()
    assert "файл отсутствует" not in check(repo)["message"]
