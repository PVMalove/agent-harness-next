"""Unit tests of the structured coordinator client; a fake runner stands in for every process."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from harness.console.coordinator_api import (
    ALLOWED_PATHS,
    ArgvError,
    CoordinatorApi,
    Outcome,
    cleanup_argv,
    coordinator_argv,
    forbidden_in,
    parse_documents,
)

REPO = Path("/work/project")


class FakeRunner:
    def __init__(self, stdout: str = "", stderr: str = "", code: int = 0) -> None:
        self.reply = (stdout, stderr, code)
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        self.calls.append((list(argv), cwd))
        stdout, stderr, code = self.reply
        return subprocess.CompletedProcess(list(argv), code, stdout, stderr)


def _call(runner: FakeRunner, path: tuple[str, ...], **values: object):  # type: ignore[no-untyped-def]
    return CoordinatorApi(REPO, runner).call(path, values)  # type: ignore[arg-type]


def test_a_json_document_with_exit_zero_is_a_document() -> None:
    runner = FakeRunner(json.dumps({"batches": []}))
    result = _call(runner, ("batch", "list"))
    assert result.outcome is Outcome.DOCUMENT and result.ok
    assert result.document == {"batches": []}
    assert runner.calls[0][1] == REPO


def test_exit_two_with_a_document_is_a_refusal_never_a_success() -> None:
    runner = FakeRunner(json.dumps({"outcome": "refused", "diagnostics": []}), code=2)
    result = _call(runner, ("recovery", "status"), batch="b-1")
    assert result.outcome is Outcome.REFUSED and not result.ok
    assert result.document and result.document["outcome"] == "refused"


def test_exit_two_without_a_document_keeps_stderr_verbatim_as_opaque_text() -> None:
    stderr = "ERROR: image missing\nREMEDY: build harness-worker:local"
    runner = FakeRunner("", stderr, 2)
    result = _call(runner, ("dispatch", "propose"), batch="b-1")
    assert result.outcome is Outcome.FAILED
    assert result.documents == ()
    assert result.stderr == stderr and result.problem_text == stderr


def test_success_with_unreadable_stdout_is_unparsed_not_ok() -> None:
    result = _call(FakeRunner("not json at all"), ("batch", "list"))
    assert result.outcome is Outcome.UNPARSED and not result.ok
    assert result.problem_text == "not json at all"
    assert _call(FakeRunner(""), ("batch", "list")).outcome is Outcome.UNPARSED


def test_a_process_that_cannot_start_is_unavailable() -> None:
    def broken(*args: object, **kwargs: object) -> "subprocess.CompletedProcess[str]":
        raise OSError("no interpreter")

    result = CoordinatorApi(REPO, broken).call(("batch", "list"))
    assert result.outcome is Outcome.UNAVAILABLE
    assert "no interpreter" in result.problem_text


def test_two_back_to_back_documents_of_cleanup_apply_keep_the_result() -> None:
    plan: dict[str, object] = {"plan": {"remove": [], "skipped": []}}
    result_doc = {"result": {"removed": ["x"], "failed": [], "skipped": []}}
    text = json.dumps(plan, indent=2) + "\n" + json.dumps(result_doc, indent=2) + "\n"
    result = CoordinatorApi(REPO, FakeRunner(text)).cleanup(apply_digest="abc")
    assert result.ok and len(result.documents) == 2
    assert result.section("result") == result_doc["result"]
    assert result.section("plan") == plan["plan"]


def test_partial_cleanup_failure_exit_one_keeps_its_documents_as_a_refusal() -> None:
    text = json.dumps({"plan": {}}) + json.dumps({"result": {"failed": [1]}})
    result = CoordinatorApi(REPO, FakeRunner(text, code=1)).cleanup(apply_digest="d")
    assert result.outcome is Outcome.REFUSED
    assert result.section("result") == {"failed": [1]}


def test_parse_documents_rejects_trailing_text_and_non_objects() -> None:
    assert parse_documents('{"a": 1}\n{"b": 2}') == (({"a": 1}, {"b": 2}), True)
    assert parse_documents('{"a": 1} tail')[1] is False
    assert parse_documents("[1, 2]") == ((), False)
    assert parse_documents("") == ((), False)


def test_argv_is_built_from_the_coordinator_parser_in_the_selected_interpreter() -> (
    None
):
    argv = coordinator_argv(
        REPO,
        ("recovery", "status"),
        {"batch": "b-1", "json": True, "skip": ["id1", "id2"]},
    )
    assert argv[1:6] == [
        ".harness/orchestration/coordinator.py",
        "--repo",
        str(REPO),
        "recovery",
        "status",
    ]
    assert argv[6:] == [
        "--batch",
        "b-1",
        "--json",
        "--skip",
        "id1",
        "--skip",
        "id2",
    ]


def test_unknown_missing_and_out_of_choice_arguments_refuse_the_build() -> None:
    with pytest.raises(ArgvError, match="no argument"):
        coordinator_argv(REPO, ("batch", "list"), {"docker": True})
    with pytest.raises(ArgvError, match="requires --batch"):
        coordinator_argv(REPO, ("dispatch", "preflight"), {"role": "qa"})
    with pytest.raises(ArgvError, match="not one of"):
        coordinator_argv(
            REPO,
            ("dispatch", "preflight"),
            {"batch": "b", "role": "qa", "purpose": "nope"},
        )


def test_only_allowlisted_commands_are_reachable() -> None:
    for path in (
        ("dispatch", "send"),
        ("batch", "abandon"),
        ("ledger", "release-lock"),
    ):
        assert path not in ALLOWED_PATHS
        with pytest.raises(ArgvError, match="not reachable"):
            coordinator_argv(REPO, path, {})


@pytest.mark.parametrize(
    "token",
    [
        "--docker",
        "--auto-approve",
        "--dangerously-skip-permissions",
        "--permission-mode",
        "--bypass-permissions",
        "--confirm",
        "--yes",
        "--force",
    ],
)
def test_forbidden_flags_are_recognised(token: str) -> None:
    assert forbidden_in(["python", "x", token]) == token


def test_a_forbidden_value_cannot_ride_inside_an_allowed_command() -> None:
    values = {"batch": "b-1", "approved_by": "--auto-approve"}
    with pytest.raises(ArgvError, match="forbidden"):
        coordinator_argv(REPO, ("dispatch", "create"), values)


def test_cleanup_is_always_soft_and_apply_is_bound_to_a_digest() -> None:
    preview = cleanup_argv(REPO)
    assert preview[-4:] == ["cleanup", str(REPO), "--mode", "soft"]
    apply = cleanup_argv(REPO, apply_digest=" d1g3st ")
    assert apply[-3:] == ["--apply", "--plan-digest", "d1g3st"]
    assert "--confirm" not in apply and "hard" not in apply
    with pytest.raises(ArgvError):
        cleanup_argv(REPO, apply_digest="  ")


# ----------------------------------------------------------------------------- contract (#711)


def test_every_command_the_client_can_build_is_free_of_forbidden_flags() -> None:
    from harness.console.coordinator_api import _fields_of

    for path in sorted(ALLOWED_PATHS):
        required = {
            dest: "x" for dest, field in _fields_of(path).items() if field.required
        }
        argv = coordinator_argv(REPO, path, required)
        assert forbidden_in(argv) is None, (path, argv)
        assert "--docker" not in argv and not any(
            "auto-approve" in token for token in argv
        )


def test_the_argv_helpers_never_carry_a_value_a_screen_could_leak() -> None:
    argv = coordinator_argv(
        REPO,
        ("dispatch", "create"),
        {
            "batch": "b-1",
            "approved_by": "operator",
            "approved_at": "2026-01-01T00:00:00+00:00",
            "transition_digest": "d" * 64,
        },
    )
    assert all(
        "=" not in token for token in argv[3:]
    )  # no NAME=value env pair rides along
    assert "--env" not in argv and "-e" not in argv


def test_the_client_module_names_no_container_engine_or_runtime_protocol() -> None:
    import harness.console.coordinator_api as client

    source = Path(client.__file__).read_text(encoding="utf-8")
    for token in (
        "docker run",
        "podman run",
        "container.observe",
        "execution.launch",
        "RuntimeClient",
    ):
        assert token not in source
