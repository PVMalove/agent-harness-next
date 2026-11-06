"""The coordinator commands of the Recovery and Container route screens over a fake console
server client: reads map to screen snapshots, recovery actions to server jobs."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from harness.console.kernel.batch_history import History, HistoryBatch, load_history
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult, ArgvError, Outcome
from harness.console.tui.client import (
    ConnectionLost,
    JobResult,
    RecoveryFacts,
    RouteFacts,
    ServerError,
)
from harness.console.tui.server_api import ServerCoordinatorApi

REPO = Path("/work/project")
STATUS = ApiResult(Outcome.DOCUMENT, ("status",), ({"batch_id": "b-1"},), 0)
PREFLIGHT = ApiResult(Outcome.REFUSED, ("preflight",), ({"verified": False},), 2)


class FakeClient:
    """The screen client methods the server API uses, recording every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.job = JobResult("completed", 0, json.dumps({"ok": True}), "", False, None)
        self.failure: Exception | None = None

    def _maybe_fail(self) -> None:
        if self.failure is not None:
            raise self.failure

    def recovery(
        self, batch: str = "", skip: Sequence[str] = (), *, force: bool = False
    ) -> RecoveryFacts:
        self.calls.append(("recovery", batch, tuple(skip)))
        self._maybe_fail()
        history = History(
            (HistoryBatch("b-1", "#1", "br", "active", "t", False, 2, 1, "qa"),)
        )
        return RecoveryFacts(history, STATUS if batch else None)

    def container_route(
        self, batch: str = "", role: str = "developer", runtime: str = ""
    ) -> RouteFacts:
        self.calls.append(("route", batch, role, runtime))
        self._maybe_fail()
        return RouteFacts(Authored({}), PREFLIGHT if batch else None)

    def run_job(
        self,
        command_id: str,
        values: Mapping[str, str],
        *,
        confirmed: bool = False,
        confirmation: str | None = None,
        plan_digest: str | None = None,
        on_output: Callable[[str, str], None] | None = None,
    ) -> JobResult:
        self.calls.append(("job", command_id, dict(values), confirmed))
        if confirmation is not None or plan_digest is not None:
            self.calls.append(("job-extra", confirmation, plan_digest))
        self._maybe_fail()
        if on_output is not None:
            on_output("stdout", self.job.stdout)
        return self.job


class NoRunner:
    def __call__(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("a server-backed call must never start a process")


def _api(client: FakeClient) -> ServerCoordinatorApi:
    return ServerCoordinatorApi(REPO, client)  # type: ignore[arg-type]


def test_the_batch_list_is_the_recovery_history_and_loads_as_the_same_history() -> None:
    client = FakeClient()
    history = load_history(_api(client))
    assert history.batches[0].batch_id == "b-1" and history.batches[0].open_dispatches == 1
    assert client.calls == [("recovery", "", ())]


def test_status_and_preflight_are_screen_snapshot_reads() -> None:
    client = FakeClient()
    api = _api(client)
    status = api.call(("recovery", "status"), {"batch": "b-1", "json": True, "skip": ["x"]})
    assert status == STATUS
    preflight = api.call(
        ("dispatch", "preflight"), {"batch": "b-1", "role": "qa", "runtime": "r"}
    )
    assert preflight == PREFLIGHT
    assert client.calls == [("recovery", "b-1", ("x",)), ("route", "b-1", "qa", "r")]


@pytest.mark.parametrize(
    ("path", "values", "command_id", "flat"),
    [
        (("recovery", "reload"), {"batch": "b", "json": True}, "recovery-reload", {"batch": "b", "json": "1"}),
        (("recovery", "abort"), {"batch": "b", "json": True}, "recovery-abort", {"batch": "b", "json": "1"}),
        (("recovery", "fix"), {"batch": "b", "json": True}, "recovery-fix", {"batch": "b", "json": "1"}),
        (
            ("recovery", "fix"),
            {"batch": "b", "json": True, "apply": True},
            "recovery-fix-apply",
            {"batch": "b", "json": "1"},
        ),
        (
            ("recovery", "resume"),
            {"batch": "b", "json": True, "approved_by": "dev", "note": ""},
            "recovery-resume",
            {"batch": "b", "json": "1", "approved_by": "dev", "note": ""},
        ),
    ],
)
def test_recovery_actions_are_server_jobs_and_forward_confirmed_only_when_given(
    path: tuple[str, ...], values: dict[str, object], command_id: str, flat: dict[str, str]
) -> None:
    client = FakeClient()
    api = _api(client)
    result = api.call(path, values)  # type: ignore[arg-type]
    assert result.ok and result.document == {"ok": True}
    assert result.argv[4 : 4 + len(path)] == path
    api.call(path, values, confirmed=True)  # type: ignore[arg-type]
    assert client.calls == [
        ("job", command_id, flat, False),
        ("job", command_id, flat, True),
    ]
    assert ("--apply" in result.argv) is (command_id == "recovery-fix-apply")


def test_a_job_refusal_or_a_lost_connection_is_unavailable_never_raised() -> None:
    client = FakeClient()
    client.failure = ServerError("confirmation_required", "confirm first")
    refused = _api(client).call(("recovery", "resume"), {"batch": "b"})
    assert refused.outcome is Outcome.UNAVAILABLE and "confirmation_required" in refused.stderr
    client.failure = ConnectionLost("gone")
    lost = _api(client).call(("recovery", "status"), {"batch": "b", "json": True})
    assert lost.outcome is Outcome.UNAVAILABLE and lost.stderr == "gone"


def test_a_job_that_failed_without_an_exit_code_is_unavailable() -> None:
    client = FakeClient()
    client.job = JobResult("failed", None, "", "", False, "executor failed")
    result = _api(client).call(("recovery", "reload"), {"batch": "b"})
    assert result.outcome is Outcome.UNAVAILABLE and result.stderr == "executor failed"


def test_without_a_fallback_a_path_the_server_does_not_serve_is_refused() -> None:
    api = _api(FakeClient())
    for path, values in (
        (("dispatch", "propose"), {"batch": "b"}),
        (("qa", "run"), {"dispatch": "d"}),
        (("dispatch", "preflight"), {"batch": "b", "role": "qa", "purpose": "work"}),
    ):
        with pytest.raises(ArgvError):
            api.call(path, values)
    with pytest.raises(ArgvError):
        api.cleanup()


def test_with_a_fallback_only_unserved_paths_reach_its_runner() -> None:
    from harness.console.kernel.coordinator_api import CoordinatorApi

    calls: list[list[str]] = []

    def runner(argv: Sequence[str], **kwargs: object) -> object:
        import subprocess

        calls.append(list(argv))
        return subprocess.CompletedProcess(list(argv), 0, "{}", "")

    client = FakeClient()
    api = ServerCoordinatorApi(
        REPO, client, fallback=CoordinatorApi(REPO, runner)  # type: ignore[arg-type]
    )
    assert api.call(("recovery", "reload"), {"batch": "b"}).ok
    assert api.call(("dispatch", "status")).ok
    assert len(calls) == 1 and calls[0][-2:] == ["dispatch", "status"]


def _report_json(fixes: list[str]) -> str:
    from harness.health.model import CheckResult, Report
    from harness.health.report_json import to_json

    report = Report(1, str(REPO), False, [CheckResult("a.b", "core", "fail", "x")], fixes)
    return json.dumps(to_json(report))


@pytest.fixture
def no_local_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """The TUI never runs health or its fixes in its own process."""
    from harness.console.kernel import data as console_data

    def local(*args: object, **kwargs: object) -> object:
        raise AssertionError("a health fix must run as a server job")

    for name in ("apply_local_fixes", "run_health", "collect_diagnostics"):
        monkeypatch.setattr(console_data, name, local)


@pytest.mark.parametrize("online", [False, True])
def test_health_fixes_are_a_confirmed_server_job_read_back_as_the_report(
    online: bool, no_local_health: None
) -> None:
    from harness.console.tui.server_api import apply_health_fixes

    client = FakeClient()
    # `harness health` exits 1 when a check fails; the fixes still ran and the report is valid.
    client.job = JobResult("completed", 1, _report_json(["a.b"]), "", False, None)
    report = apply_health_fixes(client, online=online)  # type: ignore[arg-type]
    assert report.fixes_applied == ["a.b"] and report.checks[0].status == "fail"
    key = "diagnostics-online-fix" if online else "diagnostics-fix"
    assert client.calls == [("job", key, {}, True)]


@pytest.mark.parametrize(
    "job",
    [
        JobResult("failed", None, "", "", False, "executor failed"),
        JobResult("cancelled", None, "", "", False, None),
        JobResult("completed", 2, "usage: harness", "bad flag", False, None),
    ],
    ids=["no-exit-code", "cancelled", "not-json"],
)
def test_a_health_fix_job_without_a_report_is_an_error(
    job: JobResult, no_local_health: None
) -> None:
    from harness.console.tui.client import ConsoleClientError
    from harness.console.tui.server_api import apply_health_fixes

    client = FakeClient()
    client.job = job
    with pytest.raises(ConsoleClientError) as failed:
        apply_health_fixes(client, online=False)  # type: ignore[arg-type]
    assert str(failed.value)
    if job.error or job.stderr:
        assert (job.error or job.stderr) in str(failed.value)


def test_the_server_job_runner_sends_the_form_confirmation_and_plan_digest() -> None:
    from harness.console.kernel.catalog import HARNESS_COMMANDS
    from harness.console.tui.server_api import ServerJobRunner

    entries = {entry.key: entry for entry in HARNESS_COMMANDS}
    client = FakeClient()
    client.job = JobResult("completed", 0, "removed", "", False, None)
    entry = entries["cleanup-hard-apply"]
    runner = ServerJobRunner(client, entry, {"__plan_digest": "d" * 64})  # type: ignore[arg-type]
    seen: list[tuple[str, str]] = []
    result = runner(["ignored"], cwd=REPO, on_output=lambda c, t: seen.append((c, t)))
    assert (result.returncode, result.stdout) == (0, "removed") and runner.streams_output
    assert seen == [("stdout", "removed")]
    assert client.calls == [
        ("job", "cleanup-hard-apply", {}, True),
        ("job-extra", entry.typed_confirmation, "d" * 64),
    ]
    plain = FakeClient()
    ServerJobRunner(plain, entries["health"], {})(["x"])  # type: ignore[arg-type]
    assert plain.calls == [("job", "health", {}, False)]


@pytest.mark.parametrize(
    "failure, job",
    [
        (ServerError("busy", "Busy: job-1 (update)"), None),
        (ConnectionLost("gone"), None),
        (None, JobResult("failed", None, "", "", False, "executor failed")),
    ],
    ids=["busy", "lost", "no-exit-code"],
)
def test_a_refused_or_failed_server_job_is_an_os_error_with_the_server_text(
    failure: Exception | None, job: JobResult | None
) -> None:
    from harness.console.kernel.catalog import HARNESS_COMMANDS
    from harness.console.kernel.runner import HarnessRuns
    from harness.console.tui.server_api import ServerJobRunner

    entry = next(item for item in HARNESS_COMMANDS if item.key == "update")
    client = FakeClient()
    client.failure = failure
    if job is not None:
        client.job = job
    runner = ServerJobRunner(client, entry, {})  # type: ignore[arg-type]
    with pytest.raises(OSError) as refused:
        runner(["x"])
    text = str(failure) if failure is not None else "executor failed"
    assert text in str(refused.value)
    runs = HarnessRuns()
    run = runs.reserve("update", "harness update", ["x"], {})
    assert run is not None
    runs.execute(run, runner, REPO)
    assert run.error.startswith("не удалось запустить: ") and text in run.error


def test_the_diagnostics_screen_neither_collects_nor_fixes_health_itself() -> None:
    """The screen module names no local health collection or fix; its fixes go through
    `apply_health_fixes`, the server job above."""
    import ast

    from harness.console.tui.screens import diagnostics

    tree = ast.parse(Path(diagnostics.__file__).read_text(encoding="utf-8"))
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"collect_diagnostics", "apply_local_fixes", "run_health"} & names
    assert "apply_health_fixes" in names


def test_a_harness_command_streams_its_server_job_output_into_the_run() -> None:
    from harness.console.kernel.catalog import HARNESS_COMMANDS
    from harness.console.kernel.runner import HarnessRuns
    from harness.console.tui.server_api import ServerJobRunner

    entry = next(item for item in HARNESS_COMMANDS if item.key == "health")
    client = FakeClient()
    client.job = JobResult("completed", 0, "report", "", False, None)
    runs = HarnessRuns()
    run = runs.reserve("health", "harness health", ["harness"], {})
    assert run is not None
    runs.execute(run, ServerJobRunner(client, entry, {}), REPO)  # type: ignore[arg-type]
    assert (run.phase, run.returncode, run.stdout, run.output) == (
        "completed",
        0,
        "report",
        "report",
    )
    assert client.calls == [("job", "health", {}, False)]


def test_the_repo_map_is_built_by_a_server_job_for_the_shown_head() -> None:
    from harness.console.kernel.repo_map import RepoMapView
    from harness.console.tui.server_api import build_repo_map

    from ._console_repo_map_fixture import map_payload

    head = "c" * 40
    client = FakeClient()
    client.job = JobResult("completed", 0, json.dumps(map_payload(head)), "", False, None)
    built = build_repo_map(client, head)  # type: ignore[arg-type]
    assert isinstance(built, RepoMapView) and built.commit == head
    assert client.calls == [("job", "repo-map-build", {"commit": head}, False)]

    client.job = JobResult("completed", 0, "{", "", True, None)
    truncated = build_repo_map(client, head)  # type: ignore[arg-type]
    assert isinstance(truncated, str) and "обрез" in truncated

    client.job = JobResult("completed", 2, "", "parser bundle broken", False, None)
    failed = build_repo_map(client, head)  # type: ignore[arg-type]
    assert isinstance(failed, str) and "parser bundle broken" in failed

    client.failure = ServerError("unavailable_command", "not installed")
    refused = build_repo_map(client, head)  # type: ignore[arg-type]
    assert isinstance(refused, str) and "not installed" in refused


def test_the_repo_map_screen_neither_reads_its_facts_nor_builds_the_map_itself() -> None:
    """The screen and its settings pane take HEAD, the cached map, the tier, the parsers, the
    languages and the memory status from the `repo_map.snapshot` reply, and build through
    `build_repo_map`, the server job above."""
    import ast

    from harness.console.tui.screens import repo_map, repo_map_settings

    def names(module: object) -> set[str]:
        """What the module imports and calls; a data field of the same name is neither."""
        tree = ast.parse(Path(str(getattr(module, "__file__"))).read_text(encoding="utf-8"))
        found = {
            alias.asname or alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    found.add(func.id)
                elif isinstance(func, ast.Attribute):
                    found.add(func.attr)
        return found

    local_reads = {
        "head_commit",
        "cached_map",
        "parser_status",
        "language_files",
        "memory_status",
        "tier_setting",
        "build_map",
    }
    screen, pane = names(repo_map), names(repo_map_settings)
    assert not local_reads & screen and not local_reads & pane
    assert {"build_repo_map", "repo_map"} <= screen


def test_a_memory_command_of_the_settings_pane_runs_as_a_server_job() -> None:
    from harness.console.kernel.catalog import MEMORY_COMMANDS, parsers_install_entry
    from harness.console.tui.server_api import ServerJobRunner, settings_runner

    client, local = FakeClient(), NoRunner()
    for entry in MEMORY_COMMANDS:
        runner = settings_runner(client, entry, local)  # type: ignore[arg-type]
        assert isinstance(runner, ServerJobRunner)
        runner(["harness"], cwd=REPO)
    assert [call[1] for call in client.calls] == [entry.key for entry in MEMORY_COMMANDS]
    install = parsers_install_entry(["python"])
    kept: object = settings_runner(client, install, local)  # type: ignore[arg-type]
    assert kept is local


@pytest.mark.parametrize("action", ["init", "adopt", "update"])
def test_the_installation_into_the_served_project_is_a_confirmed_server_job(
    action: str,
) -> None:
    from typing import Literal, cast

    from harness.console.kernel.project_target import ProjectTarget
    from harness.console.tui.server_api import setup_runner

    client, local = FakeClient(), NoRunner()
    target = ProjectTarget(
        REPO, cast(Literal["init", "adopt", "update"], action), (), ()
    )
    sut = setup_runner(client, REPO, target, "engineering-suite", local)  # type: ignore[arg-type]

    result = sut(["harness", action], cwd=REPO)

    assert result.returncode == 0
    assert client.calls == [
        ("job", f"setup-{action}", {"capability": "engineering-suite"}, True)
    ]


def test_the_installation_into_another_project_stays_with_the_local_runner() -> None:
    from harness.console.kernel.project_target import ProjectTarget
    from harness.console.tui.server_api import setup_runner

    client, local = FakeClient(), NoRunner()
    other = ProjectTarget(Path("/work/other"), "init", (), ())

    sut: object = setup_runner(client, REPO, other, "engineering-suite", local)  # type: ignore[arg-type]

    assert sut is local and client.calls == []


class HelpClient:
    """The `help` method of a console server client: the guide, or the client error it raises."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.languages: list[str] = []

    def help(self, language: str) -> object:
        from harness.console.kernel.help_text import help_sections

        self.languages.append(language)
        if self.failure is not None:
            raise self.failure
        return help_sections(language)


def test_the_help_screen_shows_the_guide_of_the_help_snapshot_in_the_console_language() -> None:
    from harness.console.tui.screens.help import guide_parts

    client = HelpClient()

    intro, parts = guide_parts(client, "en")  # type: ignore[arg-type]

    assert client.languages == ["en"]
    assert intro.startswith("# ") and parts[0][0] == "Console window"
    assert parts[0][1].startswith("## Console window\n")


@pytest.mark.parametrize(
    ("client", "expected"),
    [
        (None, "Help is unavailable: the console server is not connected"),
        (HelpClient(ConnectionLost("server gone")), "Help is unavailable: server gone"),
    ],
)
def test_without_an_answering_server_the_help_screen_shows_why_and_no_sections(
    client: HelpClient | None, expected: str
) -> None:
    from harness.console.tui.screens.help import guide_parts

    intro, parts = guide_parts(client, "en")  # type: ignore[arg-type]

    assert (intro, parts) == (expected, [])


def test_the_open_project_screen_reads_and_installs_the_served_project_through_the_server() -> (
    None
):
    import ast

    from harness.console.tui.screens import project_setup

    tree = ast.parse(Path(str(project_setup.__file__)).read_text(encoding="utf-8"))
    called = {
        node.func.attr
        if isinstance(node.func, ast.Attribute)
        else getattr(node.func, "id", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

    assert {"open_project", "setup_runner"} <= called
