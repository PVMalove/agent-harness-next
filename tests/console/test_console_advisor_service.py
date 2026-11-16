"""The AI advice WebSocket messages: advisor.check, advisor.ask and advisor.cancel through the
request router with a fake advisor port; no CLI process is started."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend.api.request_router import RequestRouter
from harness.console.backend.application.advisor import AdvisorService
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.jobs import JobService
from harness.console.backend.application.live_steps import LiveSteps
from harness.console.backend.application.ports import AdviceNotFound
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.backend.application.worker_steps import WorkerStepsQuery

ADVICE = {
    "outcome": "advice",
    "advice": {
        "value": "en",
        "why": "Команда",
        "impact": "Язык",
        "comparison": [{"option": "ru", "tradeoff": "Русские отчёты"}],
    },
}
STATUS = {
    "provider": "codex",
    "found": True,
    "version_supported": True,
    "authorized": False,
    "ready": False,
    "message": "Нет действующей авторизации Codex CLI.",
}


class FakePort:
    """Blocks an ask until `release` or its cancel Event; records the Events it got."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.cancels: list[threading.Event] = []
        self.asked: list[tuple[str, str, tuple[str, ...]]] = []
        self.checked: list[str] = []

    def check(self, provider: str, cancel: threading.Event) -> Mapping[str, object]:
        self.checked.append(provider)
        return {**STATUS, "provider": provider}

    def ask(
        self,
        provider: str,
        file: str,
        path: tuple[str, ...],
        cancel: threading.Event,
    ) -> Mapping[str, object]:
        if path == ("unknown",):
            raise AdviceNotFound(path)
        self.asked.append((provider, file, path))
        self.cancels.append(cancel)
        self.started.set()
        while not cancel.wait(0.01):
            if self.release.is_set():
                return ADVICE
        return {"outcome": "fallback", "cause": "refused", "reason": "Запрос ИИ отменён."}


def _router(port: FakePort, timeout: float = 5.0) -> RequestRouter:
    return RequestRouter(
        cast(SnapshotService, object()),
        cast(JobService, object()),
        cast(DecisionService, object()),
        cast(OrchestrationEvents, object()),
        cast(ScreenService, object()),
        cast(WorkerStepsQuery, object()),
        cast(LiveSteps, object()),
        advisor=AdvisorService(port, timeout=timeout),
    )


def _ask(id: object, path: list[str] | None = None, **extra: object) -> str:
    return json.dumps(
        {
            "id": id,
            "type": "advisor.ask",
            "provider": "codex",
            "file": "project.json",
            "path": path or ["language"],
            **extra,
        }
    )


async def _until(condition: object, limit: float = 3.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + limit
    while not cast(bool, condition() if callable(condition) else condition):
        if loop.time() > deadline:
            raise AssertionError("condition not reached")
        await asyncio.sleep(0.01)


class Wire:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, reply: str) -> bool:
        self.sent.append(json.loads(reply))
        return True

    def by_id(self, id: object) -> dict[str, object]:
        return next(reply for reply in self.sent if reply["id"] == id)


def test_check_reports_the_cli_status_and_never_asks() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port).open(wire.send)
        await connection.submit(
            json.dumps({"id": 1, "type": "advisor.check", "provider": "claude"})
        )
        await _until(lambda: wire.sent)
        assert wire.sent[0] == {
            "v": 1,
            "id": 1,
            "type": "advisor.check",
            "ok": True,
            "status": {**STATUS, "provider": "claude"},
        }
        assert port.checked == ["claude"] and port.asked == []
        await connection.aclose()

    asyncio.run(scenario())


def test_an_ask_returns_the_advice_of_the_named_parameter() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        port.release.set()
        connection = _router(port).open(wire.send)
        await connection.submit(_ask("a", ["language"]))
        await _until(lambda: wire.sent)
        assert wire.sent[0] == {
            "v": 1,
            "id": "a",
            "type": "advisor.ask",
            "ok": True,
            **ADVICE,
        }
        assert port.asked == [("codex", "project.json", ("language",))]
        await connection.aclose()

    asyncio.run(scenario())


def test_a_timeout_is_a_fallback_and_stops_the_cli() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port, timeout=0.05).open(wire.send)
        await connection.submit(_ask("a"))
        await _until(lambda: wire.sent)
        reply = wire.sent[0]
        assert reply["ok"] is True and reply["outcome"] == "fallback"
        assert reply["cause"] == "timeout" and reply["reason"]
        assert port.cancels[0].is_set()
        await connection.aclose()

    asyncio.run(scenario())


def test_a_cancel_frame_ends_the_ask_with_a_cancelled_fallback() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port).open(wire.send)
        await connection.submit(_ask("a"))
        await _until(port.started.is_set)
        await connection.submit(
            json.dumps({"id": "c", "type": "advisor.cancel", "request_id": "b"})
        )
        await _until(lambda: wire.sent)
        assert wire.by_id("c")["cancelled"] is False
        await connection.submit(
            json.dumps({"id": "c2", "type": "advisor.cancel", "request_id": "a"})
        )
        await _until(lambda: len(wire.sent) == 3)
        assert wire.by_id("c2")["cancelled"] is True
        assert wire.by_id("a")["outcome"] == "fallback"
        assert wire.by_id("a")["cause"] == "cancelled"
        await connection.aclose()

    asyncio.run(scenario())


def test_another_connection_cannot_cancel_an_ask() -> None:
    async def scenario() -> None:
        port, wire, other = FakePort(), Wire(), Wire()
        router = _router(port)
        connection = router.open(wire.send)
        stranger = router.open(other.send)
        await connection.submit(_ask("a"))
        await _until(port.started.is_set)
        await stranger.submit(
            json.dumps({"id": "c", "type": "advisor.cancel", "request_id": "a"})
        )
        await _until(lambda: other.sent)
        assert other.sent[0]["cancelled"] is False
        assert not port.cancels[0].is_set()
        await connection.aclose()
        await stranger.aclose()

    asyncio.run(scenario())


def test_closing_the_connection_stops_the_cli() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port).open(wire.send)
        await connection.submit(_ask("a"))
        await _until(port.started.is_set)
        await connection.aclose()
        assert port.cancels[0].is_set()

    asyncio.run(scenario())


def test_a_second_ask_is_busy_on_the_connection_and_beyond_the_global_cap() -> None:
    async def scenario() -> None:
        port = FakePort()
        router = _router(port)
        wires = [Wire() for _ in range(3)]
        connections = [router.open(wire.send) for wire in wires]
        await connections[0].submit(_ask("a"))
        await _until(lambda: len(port.asked) == 1)
        await connections[0].submit(_ask("b"))
        await _until(lambda: wires[0].sent)
        assert wires[0].by_id("b")["error"]["code"] == "busy"  # type: ignore[index]
        await connections[1].submit(_ask("a"))
        await _until(lambda: len(port.asked) == 2)
        await connections[2].submit(_ask("a"))
        await _until(lambda: wires[2].sent)
        assert wires[2].sent[0]["error"]["code"] == "busy"  # type: ignore[index]
        port.release.set()
        await _until(lambda: wires[1].sent)
        assert wires[1].sent[0]["outcome"] == "advice"
        for connection in connections:
            await connection.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "advisor.ask", "provider": "codex", "file": "project.json", "path": ["a"]},
        {"id": 1, "type": "advisor.ask", "provider": "gpt", "file": "project.json", "path": ["a"]},
        {"id": 1, "type": "advisor.ask", "provider": "codex", "file": "x.json", "path": ["a"]},
        {"id": 1, "type": "advisor.ask", "provider": "codex", "file": "project.json", "path": []},
        {"id": 1, "type": "advisor.ask", "provider": "codex", "file": "project.json", "path": ["../x"]},
        {"id": 1, "type": "advisor.ask", "provider": "codex", "file": "project.json", "path": ["a"] * 9},
        {"id": 1, "type": "advisor.ask", "provider": "codex", "file": "project.json", "path": ["a"], "value": 1},
        {"id": 1, "type": "advisor.check", "provider": "codex", "draft": {}},
        {"id": 1, "type": "advisor.check"},
        {"id": 1, "type": "advisor.cancel"},
    ],
)
def test_malformed_advisor_frames_are_refused(frame: dict[str, object]) -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port).open(wire.send)
        await connection.submit(json.dumps(frame))
        await _until(lambda: wire.sent)
        assert wire.sent[0]["error"]["code"] == "bad_request"  # type: ignore[index]
        assert port.asked == [] and port.checked == []
        await connection.aclose()

    asyncio.run(scenario())


def test_an_unknown_parameter_is_not_found() -> None:
    async def scenario() -> None:
        port, wire = FakePort(), Wire()
        connection = _router(port).open(wire.send)
        await connection.submit(_ask("a", ["unknown"]))
        await _until(lambda: wire.sent)
        assert wire.sent[0]["error"]["code"] == "not_found"  # type: ignore[index]
        await connection.aclose()

    asyncio.run(scenario())


def test_the_cli_advisor_answers_an_unknown_step_with_not_found(tmp_path: Path) -> None:
    from harness.console.backend.infrastructure.advisor import CliAdvisor
    from tests.console._configuration_fixture import installed_project

    installed_project(tmp_path)
    with pytest.raises(AdviceNotFound):
        CliAdvisor(tmp_path).ask(
            "codex", "project.json", ("no_such_parameter",), threading.Event()
        )


def test_the_cli_advisor_maps_failures_to_fallback_causes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from harness.console.backend.infrastructure import advisor as infrastructure
    from harness.console.kernel import configuration_advisor as kernel
    from tests.console._configuration_fixture import installed_project

    installed_project(tmp_path)
    for error, cause in (
        (kernel.AdviceRejected("bad"), "invalid"),
        (kernel.CliMissing("missing"), "refused"),
        (OSError("io"), "refused"),
    ):

        def advise(*_: object, error: Exception = error) -> kernel.Advice:
            raise error

        monkeypatch.setattr(infrastructure, "advise", advise)
        answer = infrastructure.CliAdvisor(tmp_path).ask(
            "codex", "project.json", ("language",), threading.Event()
        )
        assert answer["outcome"] == "fallback" and answer["cause"] == cause
        assert answer["reason"]

    monkeypatch.setattr(
        infrastructure,
        "advise",
        lambda *_: kernel.Advice("en", "why", "impact", (("ru", "trade"),)),
    )
    assert infrastructure.CliAdvisor(tmp_path).ask(
        "codex", "project.json", ("language",), threading.Event()
    ) == {
        "outcome": "advice",
        "advice": {
            "value": "en",
            "why": "why",
            "impact": "impact",
            "comparison": [{"option": "ru", "tradeoff": "trade"}],
        },
    }


@pytest.fixture(autouse=True)
def no_remote_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.console.kernel import project_facts

    monkeypatch.setattr(project_facts, "_default_branch", lambda _repo: None)
