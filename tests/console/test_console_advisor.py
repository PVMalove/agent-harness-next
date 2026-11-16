"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from threading import Event

import pytest

from harness.console.kernel.configuration import ConfigurationDraft
from harness.console.kernel.configuration_advisor import (
    Advice,
    AdvisorUnavailable,
    advise,
    build_request,
    parse_response,
)
from harness.console.kernel.configuration_steps import ConfigurationStep, steps_for
from tests.console._configuration_fixture import installed_project


def test_prompt_excludes_authored_commands_and_paths(tmp_path: Path) -> None:
    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    draft.set_value("project.json", ("qa_gate_commands",), ["echo private-command"])
    request = build_request(draft, steps_for(draft)[0])
    assert "private-command" not in request
    assert str(tmp_path) not in request
    assert '"choices": ["ru", "en"]' in request


def test_cli_uses_saved_login_and_disables_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    seen: list[list[str]] = []

    def run(
        argv: list[str],
        cwd: Path,
        prompt: str,
        cancel: Event,
        timeout: float,
        **_: object,
    ) -> str:
        seen.append(argv)
        assert cwd != tmp_path
        if "--help" in argv:
            return "--ignore-user-config --ignore-rules --ephemeral --output-schema --disable"
        if "login" in argv:
            return "Logged in using ChatGPT"
        output = Path(argv[argv.index("--output-last-message") + 1])
        output.write_text(
            json.dumps(
                {"value": "en", "why": "Общая команда", "impact": "Английские отчёты"}
            )
        )
        return ""

    monkeypatch.setattr(shutil, "which", lambda _: "/bin/codex")
    monkeypatch.setattr(advisor, "_run", run)
    result = advise("codex", draft, field, Event())
    assert result == Advice("en", "Общая команда", "Английские отчёты")
    command = seen[-1]
    assert "--ignore-user-config" in command
    assert "--ephemeral" in command
    assert "read-only" in command
    assert "shell_tool" in command and "hooks" in command
    assert not any("auth.json" in value for value in command)


def test_missing_cli_falls_back_without_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(AdvisorUnavailable, match="Обычные подсказки"):
        advise("codex", draft, steps_for(draft)[0], Event())


def test_claude_structured_output_and_rejection(tmp_path: Path) -> None:
    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    response = json.dumps(
        {"structured_output": {"value": "en", "why": "Команда", "impact": "Язык"}}
    )
    assert parse_response(response, field).value == "en"
    with pytest.raises(AdvisorUnavailable):
        parse_response('{"value":"invented","why":"x","impact":"y"}', field)
    with pytest.raises(AdvisorUnavailable):
        parse_response('{"value":"en","why":"token=secret","impact":"y"}', field)


def test_claude_reuses_auth_and_never_uses_bare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    seen: list[list[str]] = []

    def run(
        argv: list[str],
        cwd: Path,
        prompt: str,
        cancel: Event,
        timeout: float,
        **_: object,
    ) -> str:
        seen.append(argv)
        if "--help" in argv:
            return "--safe-mode --tools --strict-mcp-config --no-session-persistence --json-schema"
        if "auth" in argv:
            return '{"loggedIn": true}'
        assert cwd != tmp_path and timeout == 90
        return '{"structured_output":{"value":"en","why":"Команда","impact":"Язык"}}'

    monkeypatch.setattr(shutil, "which", lambda _: "/bin/claude")
    monkeypatch.setattr(advisor, "_run", run)
    assert advise("claude", draft, steps_for(draft)[0], Event()).value == "en"
    assert "--safe-mode" in seen[-1] and "--bare" not in seen[-1]
    assert seen[-1][seen[-1].index("--tools") + 1] == ""
    assert not any("login" in command or "logout" in command for command in seen)


@pytest.mark.parametrize(
    ("status", "ready"),
    [
        ("Logged in using ChatGPT", True),
        ("WARNING: aliases\nLogged in using an API key", True),
        ("Not logged in", False),
        ("not logged in; run login", False),
    ],
)
def test_codex_login_status_is_matched_by_leading_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, ready: bool
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    def run(
        argv: list[str],
        cwd: Path,
        prompt: str,
        cancel: Event,
        timeout: float,
        **_: object,
    ) -> str:
        if "--help" in argv:
            return "--ignore-user-config --ignore-rules --ephemeral --output-schema --disable"
        return status

    monkeypatch.setattr(shutil, "which", lambda _: "/bin/codex")
    monkeypatch.setattr(advisor, "_run", run)
    result = advisor.availability("codex", Event())
    assert result.startswith("Готов") is ready


def test_comparison_is_validated_and_context_carries_only_non_secret_facts(
    tmp_path: Path,
) -> None:
    installed_project(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    request = build_request(draft, field)
    assert '"project_markers": ["pyproject.toml"]' in request
    assert "comparison" in request and str(tmp_path) not in request
    good = {
        "value": "en",
        "why": "Команда",
        "impact": "Язык",
        "comparison": [{"option": "ru", "tradeoff": "Русские отчёты"}],
    }
    assert parse_response(json.dumps(good), field).comparison == (
        ("ru", "Русские отчёты"),
    )
    for bad in (
        {**good, "comparison": [{"option": "a"}]},
        {**good, "comparison": [{"option": "a", "tradeoff": "b"}] * 5},
        {**good, "comparison": [{"option": "a", "tradeoff": "token=hidden1"}]},
    ):
        with pytest.raises(AdvisorUnavailable):
            parse_response(json.dumps(bad), field)


def test_a_response_in_a_code_fence_or_with_an_encoded_value_is_accepted(
    tmp_path: Path,
) -> None:
    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    body = '{"value": "\\"en\\"", "why": "Команда", "impact": "Язык"}'
    advice = parse_response("Вот ответ:\n```json\n" + body + "\n```", field)
    assert advice.value == "en"
    assert parse_response(body, field).value == "en"
    assert parse_response('{"value":"en","why":"x","impact":"y","note":"?"}', field)


def test_a_rejected_response_names_the_reason(tmp_path: Path) -> None:
    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    for raw, reason in (
        ("не JSON", "не в формате JSON"),
        ('{"value":"en","why":"x"}', "нет полей impact"),
        ('{"value":"invented","why":"x","impact":"y"}', "не проходит проверку поля"),
        ('{"value":"en","why":"token=secret","impact":"y"}', "похож на секрет"),
    ):
        with pytest.raises(AdvisorUnavailable, match=reason):
            parse_response(raw, field)


_REQUEST_KEYS = {
    "file",
    "parameter",
    "type",
    "choices",
    "more_choices",
    "description",
    "platform",
    "project_markers",
    "qa_command_detected",
    "value_already_set",
    "console_recommendation",
}


def _two_values(field: ConfigurationStep) -> tuple[object, object] | None:
    if field.kind == "array" and field.choices:
        candidates: list[object] = [[field.choices[0]], list(field.choices[:2])]
    elif field.choices:
        candidates = list(field.choices)
    elif field.kind == "boolean":
        candidates = [True, False]
    elif field.kind in {"integer", "number"}:
        candidates = [1, 2, 3, 5, 10, 60, 600, 3600]
    elif field.kind == "string":
        candidates = ["alpha-value", "beta-value"]
    else:
        return None
    valid = []
    for candidate in candidates:
        try:
            field.validate(candidate)
        except ValueError:
            continue
        valid.append(candidate)
    return (valid[0], valid[1]) if len(valid) >= 2 else None


def test_the_request_carries_no_secret_path_command_model_or_current_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from harness.console.kernel.configuration_advisor import request_context
    from harness.health import project_tracker
    from tests.console._configuration_fixture import _orchestration_project

    monkeypatch.setattr(
        project_tracker,
        "resolve_project_tracker",
        lambda _repo: SimpleNamespace(effective=SimpleNamespace(type="local")),
    )
    _orchestration_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json", "orchestration.json"))
    sentinels = (
        "sentinel-private-qa-command",
        "/opt/sentinel/absolute/path",
        str(tmp_path),
        "sentinel-model-name-x9",
        "ghp_SentinelTokenValue0123456789abcdefABCD",
        "sentinel-branch-current",
    )
    draft.set_value(
        "project.json", ("qa_gate_commands",), ["sentinel-private-qa-command"]
    )
    draft.set_value("project.json", ("base_branch",), "sentinel-branch-current")
    draft.set_value("project.json", ("branch_pattern",), "/opt/sentinel/absolute/path")
    draft.set_value(
        "orchestration.json",
        ("assignment_plans", "architect", "runtimes", "claude", "model"),
        "sentinel-model-name-x9",
    )
    draft.set_value(
        "orchestration.json",
        ("developer_verification_commands",),
        ["ghp_SentinelTokenValue0123456789abcdefABCD"],
    )
    steps = steps_for(draft)
    assert len(steps) > 10
    checked = 0
    for field in steps:
        request = build_request(draft, field)
        for sentinel in sentinels:
            assert sentinel not in request, (field.path, sentinel)
        context = request_context(draft, field)
        assert set(context) == _REQUEST_KEYS, field.path
        values = _two_values(field)
        if values is None:
            continue
        snapshots = []
        for value in values:
            draft.set_value(field.file, field.path, value)
            snapshots.append(request_context(draft, field))
        assert snapshots[0] == snapshots[1], field.path
        assert snapshots[0]["value_already_set"] is True
        checked += 1
    assert checked > 5


def test_the_language_recommendation_does_not_echo_the_current_value(
    tmp_path: Path,
) -> None:
    from harness.console.kernel.configuration_advisor import request_context

    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = next(s for s in steps_for(draft) if s.path == ("language",))
    recommendations = set()
    for value in ("ru", "en"):
        draft.set_value("project.json", ("language",), value)
        recommendations.add(request_context(draft, field)["console_recommendation"])
        # The wizard text still offers to keep the current setting.
        assert field.recommendation(draft)[0] == value
    assert len(recommendations) == 1


def _fake_cli(
    monkeypatch: pytest.MonkeyPatch,
    help_text: str,
    status: str,
    seen: list[list[str]],
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    def run(
        argv: list[str],
        cwd: Path,
        prompt: str,
        cancel: Event,
        timeout: float,
        **_: object,
    ) -> str:
        seen.append(argv)
        if "--help" in argv:
            return help_text
        if "login" in argv or "auth" in argv:
            return status
        raise AssertionError("check_cli must never call a model")

    monkeypatch.setattr(advisor, "_run", run)


_CODEX_HELP = (
    "--ignore-user-config --ignore-rules --ephemeral --output-schema --disable"
)
_CLAUDE_HELP = (
    "--safe-mode --tools --strict-mcp-config --no-session-persistence --json-schema"
)


@pytest.mark.parametrize(
    ("provider", "which", "help_text", "status", "expected"),
    [
        ("codex", None, _CODEX_HELP, "Logged in", (False, None, None, False)),
        ("codex", "/bin/codex", "--disable", "Logged in", (True, False, None, False)),
        ("codex", "/bin/codex", _CODEX_HELP, "Not logged in", (True, True, False, False)),
        ("codex", "/bin/codex", _CODEX_HELP, "Logged in", (True, True, True, True)),
        ("claude", "/bin/claude", "--tools", '{"loggedIn": true}', (True, False, None, False)),
        ("claude", "/bin/claude", _CLAUDE_HELP, '{"loggedIn": false}', (True, True, False, False)),
        ("claude", "/bin/claude", _CLAUDE_HELP, "garbage", (True, True, None, False)),
        ("claude", "/bin/claude", _CLAUDE_HELP, '{"loggedIn": true}', (True, True, True, True)),
    ],
)
def test_check_cli_reports_presence_version_and_authorization_without_a_model(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    which: str | None,
    help_text: str,
    status: str,
    expected: tuple[bool, bool | None, bool | None, bool],
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    seen: list[list[str]] = []
    _fake_cli(monkeypatch, help_text, status, seen)
    monkeypatch.setattr(shutil, "which", lambda _: which)
    result = advisor.check_cli(provider, Event())
    assert (
        result.found,
        result.version_supported,
        result.authorized,
        result.ready,
    ) == expected
    assert result.provider == provider and result.message
    assert advisor.availability(provider, Event()) == result.message
    assert all("--help" in argv or "status" in argv for argv in seen), seen


def test_failures_are_typed_and_keep_their_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.kernel import configuration_advisor as advisor

    installed_project(tmp_path)
    draft = ConfigurationDraft.load(tmp_path, ("project.json",))
    field = steps_for(draft)[0]
    for error in (
        advisor.CliMissing,
        advisor.CliUnsupported,
        advisor.CliUnauthorized,
        advisor.AdviceRejected,
    ):
        assert issubclass(error, AdvisorUnavailable)
    with pytest.raises(advisor.AdviceRejected, match="не в формате JSON"):
        parse_response("не JSON", field)
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(advisor.CliMissing, match="CLI не найден"):
        advise("codex", draft, field, Event())
    seen: list[list[str]] = []
    monkeypatch.setattr(shutil, "which", lambda _: "/bin/codex")
    _fake_cli(monkeypatch, "--disable", "Logged in", seen)
    with pytest.raises(advisor.CliUnsupported, match="не поддерживает"):
        advise("codex", draft, field, Event())
    _fake_cli(monkeypatch, _CODEX_HELP, "Not logged in", seen)
    with pytest.raises(advisor.CliUnauthorized, match="авторизации Codex"):
        advise("codex", draft, field, Event())


@pytest.fixture(autouse=True)
def no_remote_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.console.kernel import project_facts

    monkeypatch.setattr(project_facts, "_default_branch", lambda _repo: None)
