"""The screen snapshot requests round-trip through the FastAPI application: the real /ws route
and its security middleware, driven in process over ASGI with fake screen facts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.request_router import RequestRouter
from harness.console.backend.api.schemas import REPLIES
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel.batch_history import History
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult
from harness.console.kernel.harness_facts import HarnessState
from harness.console.kernel.health_report import report_from_payload
from harness.console.kernel.repo_map_settings import MemoryStatus
from harness.console.kernel.repo_map_snapshot import RepoMapFacts
from harness.console.kernel.reports import ledger_from_payload, timeline_from_payload
from harness.console.kernel.screen_views import recovery_view_payload, route_view_payload

from ._asgi_ws import AsgiWebSocket, Rejected
from ._screen_facts import (
    BODY,
    HARNESS_STATE,
    Facts,
    health_report,
    open_project_facts,
    repo_map_facts,
    service,
)

PORT = 48123
TOKEN = "t" * 43


class Runtime:
    """The server facts the transport reads; its router is the composition's."""

    port = PORT
    token = TOKEN
    closing = False

    def __init__(self, router: RequestRouter, static_root: Path) -> None:
        self.router = router
        self.static_root = static_root
        self.clients = 0

    def client_opened(self) -> None:
        self.clients += 1

    def client_closed(self) -> None:
        self.clients -= 1


def _runtime(tmp_path: Path, facts: Facts) -> Runtime:
    parts = composition.compose(
        tmp_path,
        snapshots=cast(SnapshotService, object()),
        jobs=cast(JobService, object()),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=service(facts),
    )
    return Runtime(parts.router, tmp_path / "no-build")


async def _read(socket: AsgiWebSocket, request: dict[str, object]) -> object:
    await socket.send_text(json.dumps({"id": 1, **request}))
    reply = json.loads(await socket.receive_text())
    assert reply["ok"] is True, reply
    text, snapshot_id = reply["text"], reply["snapshot_id"]
    page = 2
    while not reply["done"]:
        await socket.send_text(
            json.dumps(
                {
                    "id": page,
                    "type": "snapshot.page",
                    "snapshot_id": snapshot_id,
                    "offset": reply["next"],
                }
            )
        )
        reply = json.loads(await socket.receive_text())
        assert reply["ok"] is True and reply["id"] == page, reply
        text += reply["text"]
        page += 1
    return json.loads(text)


def test_every_screen_request_round_trips_through_the_websocket_route(
    tmp_path: Path,
) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            assert runtime.clients == 1
            view = ledger_from_payload(await _read(socket, {"type": "reports.snapshot"}))
            assert view.reports[0].dispatch_id == "d-1"
            body = await _read(socket, {"type": "reports.report", "dispatch_id": "d-1"})
            assert body == {"output": BODY}
            timeline = await _read(
                socket, {"type": "reports.timeline", "batch_id": "b-1"}
            )
            assert timeline_from_payload(timeline).batch.batch_id == "b-1"
            orchestration = await _read(socket, {"type": "orchestration.snapshot"})
            assert isinstance(orchestration, dict)
            assert orchestration["lock"] == {"lock": {"locked": False}, "error": None}
            recovery = await _read(
                socket, {"type": "recovery.snapshot", "batch": "b-1"}
            )
            assert isinstance(recovery, dict)
            assert History.from_payload(recovery["history"]).find("b-1") is not None
            assert ApiResult.from_payload(recovery["status"]).ok
            route = await _read(
                socket, {"type": "container_route.snapshot", "batch": "b-1"}
            )
            assert isinstance(route, dict)
            assert Authored.from_payload(route["authored"]).document == {"roles": {}}
            assert facts.preflights == [("b-1", "developer", "")]
            recovery_view = await _read(
                socket, {"type": "recovery.view", "batch": "b-1", "skip": ["a1"]}
            )
            assert recovery_view == recovery_view_payload(
                facts.history(tmp_path),
                ApiResult.from_payload(recovery["status"]),
                "b-1",
                ("a1",),
            )
            assert facts.statuses[-1] == ("b-1", ("a1",))
            route_view = await _read(
                socket, {"type": "container_route.view", "batch": "b-1", "role": "qa"}
            )
            assert route_view == route_view_payload(
                Authored({"roles": {}}),
                facts.preflight(tmp_path, "b-1", "qa", ""),
                "b-1",
                "qa",
                "",
            )
            assert facts.preflights[-2] == ("b-1", "qa", "")
            await socket.send_text(json.dumps({"id": "l", "type": "orchestration.lock"}))
            lock = json.loads(await socket.receive_text())
            assert lock == {
                "v": 1,
                "id": "l",
                "type": "orchestration.lock",
                "ok": True,
                "lock": {"locked": False},
                "error": None,
            }
            await socket.send_text(
                json.dumps({"id": 9, "type": "reports.report", "dispatch_id": "d-9"})
            )
            missing = json.loads(await socket.receive_text())
            assert missing["error"]["code"] == "not_found" and missing["id"] == 9
            for bad in (
                {"type": "recovery.view", "skip": "a1"},
                {"type": "recovery.view", "online": True},
                {"type": "container_route.view", "role": ""},
            ):
                await socket.send_text(json.dumps({"id": 10, **bad}))
                refused = json.loads(await socket.receive_text())
                assert refused["error"]["code"] == "bad_request", refused
            await socket.send_text(json.dumps({"id": 11, "type": "container_route.view"}))
            first = json.loads(await socket.receive_text())
            assert first["cached"] is False and first["age_seconds"] == 0
            assert REPLIES.validate_python(first).type == "container_route.view"
        assert runtime.clients == 0

    asyncio.run(scenario())


def test_the_diagnostics_and_harness_snapshots_round_trip_and_are_cached(
    tmp_path: Path,
) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def ask(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
        await socket.send_text(json.dumps({"id": 1, **request}))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            offline = await _read(socket, {"type": "diagnostics.snapshot"})
            assert report_from_payload(offline) == health_report()
            online = await _read(socket, {"type": "diagnostics.snapshot", "online": True})
            assert report_from_payload(online) == health_report(online=True)
            cached = await ask(socket, {"type": "diagnostics.snapshot"})
            assert cached["cached"] is True and cached["done"] is True
            forced = await ask(socket, {"type": "diagnostics.snapshot", "force": True})
            assert forced["cached"] is False
            assert (facts.calls["health"], facts.calls["health_online"]) == (2, 1)

            harness = await _read(socket, {"type": "harness.snapshot"})
            assert isinstance(harness, dict)
            assert HarnessState.from_payload(harness["state"]) == HARNESS_STATE
            assert (harness["package_version"], harness["drift"]) == ("1.0.1", "clean")
            assert ledger_from_payload(harness["ledger"]).batches[0].batch_id == "b-1"
            assert (await ask(socket, {"type": "harness.snapshot"}))["cached"] is True
            assert facts.calls["harness"] == 1

            overview = await ask(socket, {"type": "harness.overview"})
            assert REPLIES.validate_python(overview) is not None
            assert HarnessState.from_payload(overview["state"]) == HARNESS_STATE
            assert (overview["package_version"], overview["drift"]) == ("1.0.1", "clean")
            # The same counts the TUI shows in its usage line for this ledger.
            assert overview["usage"] == {
                "unavailable": None,
                "batches": 1,
                "tickets": 1,
                "dispatches": 1,
                "reports": 1,
            }
            assert overview["cached"] is True and facts.calls["harness"] == 1
            assert "ledger" not in overview and "snapshot_id" not in overview

            maintenance = await _read(socket, {"type": "harness.maintenance"})
            assert maintenance == {"maintenance": None, "error": "Git unavailable"}
            again = await ask(socket, {"type": "harness.maintenance", "force": True})
            assert again["cached"] is False and facts.calls["maintenance"] == 2

            requests: list[dict[str, object]] = [
                {"type": "diagnostics.snapshot", "extra": 1},
                {"type": "diagnostics.snapshot", "online": "yes"},
                {"type": "harness.snapshot", "online": True},
                {"type": "harness.overview", "online": True},
                {"type": "harness.overview", "force": "yes"},
                {"type": "harness.maintenance", "force": 1},
            ]
            for broken in requests:
                refused = await ask(socket, broken)
                error = refused["error"]
                assert refused["ok"] is False and refused["type"] == broken["type"]
                assert isinstance(error, dict) and error["code"] == "bad_request"
            facts.collect_error = RuntimeError("secret /home/x")
            failed = await ask(socket, {"type": "diagnostics.snapshot", "force": True})
            assert failed["error"] == {"code": "collect_failed", "message": "RuntimeError"}

    asyncio.run(scenario())


def test_the_repo_map_snapshot_round_trips_and_is_cached(tmp_path: Path) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def ask(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
        await socket.send_text(json.dumps({"id": 1, **request}))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found = await _read(socket, {"type": "repo_map.snapshot"})
            assert RepoMapFacts.from_payload(found) == repo_map_facts()
            cached = await ask(socket, {"type": "repo_map.snapshot"})
            assert cached["cached"] is True and facts.calls["repo_map"] == 1
            forced = await ask(socket, {"type": "repo_map.snapshot", "force": True})
            assert forced["cached"] is False and facts.calls["repo_map"] == 2
            requests: list[dict[str, object]] = [
                {"type": "repo_map.snapshot", "extra": 1},
                {"type": "repo_map.snapshot", "force": "yes"},
            ]
            for broken in requests:
                refused = await ask(socket, broken)
                error = refused["error"]
                assert refused["ok"] is False and isinstance(error, dict)
                assert error["code"] == "bad_request"

    asyncio.run(scenario())


def test_the_open_project_and_help_snapshots_round_trip_and_no_request_switches_the_project(
    tmp_path: Path,
) -> None:
    from harness.console.kernel.help_text import HelpSections, help_sections
    from harness.console.kernel.open_project_snapshot import OpenProjectFacts

    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def ask(
        socket: AsgiWebSocket, request: dict[str, object]
    ) -> dict[str, object]:
        await socket.send_text(json.dumps({"id": 1, **request}))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found = await _read(socket, {"type": "open_project.snapshot"})
            assert OpenProjectFacts.from_payload(found) == open_project_facts()
            cached = await ask(socket, {"type": "open_project.snapshot"})
            assert cached["cached"] is True and facts.calls["open_project"] == 1
            forced = await ask(socket, {"type": "open_project.snapshot", "force": True})
            assert forced["cached"] is False and facts.calls["open_project"] == 2

            english = await _read(socket, {"type": "help.snapshot", "language": "en"})
            assert HelpSections.from_payload(english) == help_sections("en")
            russian = await _read(socket, {"type": "help.snapshot", "language": "ru"})
            assert HelpSections.from_payload(russian).intro.startswith("# Справка")

            requests: list[dict[str, object]] = [
                {"type": "open_project.snapshot", "repo": "/work/other"},
                {"type": "open_project.snapshot", "force": "yes"},
                {"type": "help.snapshot"},
                {"type": "help.snapshot", "language": "de"},
            ]
            for broken in requests:
                refused = await ask(socket, broken)
                error = refused["error"]
                assert refused["ok"] is False and isinstance(error, dict)
                assert error["code"] == "bad_request"

    asyncio.run(scenario())


def test_the_repo_map_facts_of_a_project_without_git_have_no_head_and_no_map(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.backend.infrastructure import screen_facts

    def unreadable(repo: Path) -> object:
        raise OSError("no registry")

    monkeypatch.setattr(screen_facts, "parser_status", unreadable)
    monkeypatch.setattr(screen_facts, "head_commit", lambda repo: None)
    monkeypatch.setattr(screen_facts, "language_files", lambda repo: {})
    memory = MemoryStatus(False, False, (), None, "нет Git")
    monkeypatch.setattr(screen_facts, "memory_status", lambda repo: memory)
    found = RepoMapFacts.from_payload(screen_facts.repo_map_facts(tmp_path))
    assert (found.head, found.view, found.parsers) == (None, None, None)
    assert found.tier.editable is False and found.language_files == {}
    assert found.memory == memory
    assert composition.screen_service(tmp_path)._collect_repo_map is (
        screen_facts.repo_map_facts
    )


def test_the_job_service_builds_the_repo_map_of_the_given_commit(tmp_path: Path) -> None:
    """The map is built by the server as the `repo-map-build` job for the commit the screen
    showed, with the Repo Map CLI of the harness package, so a project without an installed copy
    still builds, and `-B` keeps `__pycache__` out of the project."""
    from harness.console.backend.domain.jobs import JobRejected
    from harness.console.kernel.catalog import REPO_MAP_BUILD, REPO_MAP_COMMANDS

    from ._screen_facts import HEAD

    ran: list[list[str]] = []

    async def executor(
        argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        ran.append(list(cast(list[str], argv)))
        cast(Callable[[str, str], None], on_output)("stdout", "{}")
        return 0

    async def scenario() -> None:
        served = composition.job_service(tmp_path, executor=executor)
        # A known command without its commit is a bad request, never an unknown command.
        with pytest.raises(JobRejected) as refused:
            served.start({"command_id": "repo-map-build", "client": "tui"})
        assert refused.value.code == "bad_request" and ran == []
        jobs = JobService(
            tmp_path,
            catalog={entry.key: entry for entry in REPO_MAP_COMMANDS},
            executor=executor,
            journal=lambda repo, record: None,
            new_id=lambda: "job-1",
            now=lambda: "t",
        )
        job = jobs.start(
            {"command_id": "repo-map-build", "values": {"commit": HEAD}, "client": "tui"}
        )
        while job.phase == "running":
            await asyncio.sleep(0.01)
        assert (job.phase, job.returncode) == ("completed", 0)
        script = Path(ran[0][2])
        assert ran[0][1] == "-B" and script.is_absolute() and script.is_file()
        assert (script.parent.name, script.name) == ("repo_map", "repo_map.py")
        assert ran[0][3:] == ["--repo", str(tmp_path), "--commit", HEAD]
        assert not REPO_MAP_BUILD.read_only and not REPO_MAP_BUILD.needs_confirmation

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "headers",
    [
        [(b"host", f"127.0.0.1:{PORT}".encode())],
        [
            (b"host", f"127.0.0.1:{PORT}".encode()),
            (b"authorization", b"Bearer wrong"),
        ],
        [(b"host", b"evil.example"), (b"authorization", f"Bearer {TOKEN}".encode())],
    ],
    ids=["no-token", "wrong-token", "foreign-host"],
)
def test_the_security_middleware_refuses_a_screen_client_without_the_session(
    tmp_path: Path, headers: list[tuple[bytes, bytes]]
) -> None:
    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def scenario() -> None:
        with pytest.raises(Rejected) as refused:
            async with AsgiWebSocket(
                create_app(runtime), PORT, TOKEN, headers=headers
            ):
                pass
        assert refused.value.status in (401, 403)

    asyncio.run(scenario())
    assert facts.calls == {} and runtime.clients == 0


def test_the_job_service_runs_a_diagnostics_fix_only_as_confirmed(tmp_path: Path) -> None:
    """An online fix changes the tracker: it starts only confirmed, then runs as a server job
    whose stdout is the `--json` report."""
    from harness.console.backend.domain.jobs import JobRejected
    from harness.console.kernel.catalog import DIAGNOSTICS_COMMANDS
    from harness.health.report_json import to_json

    from ._screen_facts import health_report

    ran: list[list[str]] = []
    journal: list[dict[str, object]] = []

    async def executor(
        argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        ran.append(list(cast(list[str], argv)))
        cast(Callable[[str, str], None], on_output)(
            "stdout", json.dumps(to_json(health_report()))
        )
        return 1

    async def scenario() -> None:
        served = composition.job_service(tmp_path, executor=executor)
        with pytest.raises(JobRejected) as refused:
            served.start({"command_id": "diagnostics-online-fix", "client": "tui"})
        assert refused.value.code == "confirmation_required" and ran == []
        # The same catalog entry with an in-memory journal: the real one resolves Git.
        jobs = JobService(
            tmp_path,
            catalog={entry.key: entry for entry in DIAGNOSTICS_COMMANDS},
            executor=executor,
            journal=lambda repo, record: journal.append(dict(record)),
            new_id=lambda: "job-1",
            now=lambda: "t",
        )
        job = jobs.start(
            {"command_id": "diagnostics-online-fix", "client": "tui", "confirmed": True}
        )
        while job.phase == "running":
            await asyncio.sleep(0.01)
        assert (job.phase, job.returncode) == ("completed", 1)
        output = "".join(fragment.text for fragment in job.output)
        assert report_from_payload(json.loads(output)) == health_report()
        assert ran[0][-3:] == ["--online", "--fix", "--json"]
        assert journal[0]["command_id"] == "diagnostics-online-fix"

    asyncio.run(scenario())


def test_the_update_harness_snapshot_and_a_diff_of_a_drifted_file_round_trip(
    tmp_path: Path,
) -> None:
    from harness.console.kernel.update_harness_snapshot import UpdateHarnessFacts

    from ._screen_facts import UPDATE_DRIFT

    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def ask(
        socket: AsgiWebSocket, request: dict[str, object]
    ) -> dict[str, object]:
        await socket.send_text(json.dumps({"id": 1, **request}))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found = UpdateHarnessFacts.from_payload(
                await _read(socket, {"type": "update_harness.snapshot"})
            )
            assert (found.state, found.package_version) == (HARNESS_STATE, "1.0.1")
            assert found.drift == UPDATE_DRIFT
            cached = await ask(socket, {"type": "update_harness.snapshot"})
            assert cached["cached"] is True and facts.calls["update_harness"] == 1

            diff = await _read(
                socket, {"type": "update_harness.diff", "path": "AGENTS.md"}
            )
            assert diff == {
                "path": "AGENTS.md",
                "text": "--- проект/AGENTS.md\n+++ после обновления/AGENTS.md\n",
            }
            assert facts.diffs == ["AGENTS.md"] and facts.calls["update_harness"] == 1

            for outside in ("../secret.txt", "harness/other.py", "/etc/passwd"):
                refused = await ask(
                    socket, {"type": "update_harness.diff", "path": outside}
                )
                error = refused["error"]
                assert refused["ok"] is False and isinstance(error, dict)
                assert error["code"] == "not_found", outside
            assert facts.diffs == ["AGENTS.md"]

            requests: list[dict[str, object]] = [
                {"type": "update_harness.snapshot", "path": "x"},
                {"type": "update_harness.snapshot", "force": "yes"},
                {"type": "update_harness.diff"},
                {"type": "update_harness.diff", "path": ""},
                {"type": "update_harness.diff", "path": "a" * 513},
                {"type": "update_harness.diff", "path": "AGENTS.md", "force": 1},
            ]
            for broken in requests:
                refused = await ask(socket, broken)
                error = refused["error"]
                assert refused["ok"] is False and isinstance(error, dict)
                assert error["code"] == "bad_request", broken
            assert facts.diffs == ["AGENTS.md"]

    asyncio.run(scenario())


def test_the_configuration_snapshot_round_trips_and_is_cached(tmp_path: Path) -> None:
    from harness.console.kernel.configuration_snapshot import ConfigurationFacts

    from ._screen_facts import CONFIGURATION_FACTS

    facts = Facts()
    runtime = _runtime(tmp_path, facts)

    async def ask(
        socket: AsgiWebSocket, request: dict[str, object]
    ) -> dict[str, object]:
        await socket.send_text(json.dumps({"id": 1, **request}))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found = await _read(socket, {"type": "configuration.snapshot"})
            assert ConfigurationFacts.from_payload(found) == CONFIGURATION_FACTS
            cached = await ask(socket, {"type": "configuration.snapshot"})
            assert cached["cached"] is True and facts.calls["configuration"] == 1
            forced = await ask(socket, {"type": "configuration.snapshot", "force": True})
            assert forced["cached"] is False and facts.calls["configuration"] == 2
            requests: list[dict[str, object]] = [
                {"type": "configuration.snapshot", "recover": True},
                {"type": "configuration.snapshot", "force": "yes"},
            ]
            for broken in requests:
                refused = await ask(socket, broken)
                error = refused["error"]
                assert refused["ok"] is False and isinstance(error, dict)
                assert error["code"] == "bad_request"

    asyncio.run(scenario())
