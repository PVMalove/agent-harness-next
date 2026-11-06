"""A browser runs a catalog command through the FastAPI application: the real /ws route with the
session cookie, the job service of the composition over a fake executor, and the ru/en labels the
web console shows for the commands, their confirmation and the job refusals."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.admission import cookie_name
from harness.console.backend.api.protocol.jobs import _ERRORS
from harness.console.backend.api.request_router import RequestRouter
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.backend.application.screens import ScreenService
from harness.console.backend.domain.approvals import CANCEL_KEEPS_CHANGES
from harness.console.backend.infrastructure import command_journal
from harness.console.kernel import web_catalog
from harness.console.kernel.catalog import CONFIRMATION_REASONS, REVERSIBILITY_LABELS

from ._asgi_ws import AsgiWebSocket

PORT = 48124
TOKEN = "c" * 43

# What the web console shows for each job refusal code (`ws/jobs.ts`, `JOB_ERROR_LABELS`).
JOB_ERROR_LABELS = {
    "unknown_command": "Неизвестная команда каталога",
    "confirmation_required": "Команда требует явного подтверждения",
    "plan_required": "Сначала нужно превью плана очистки",
    "unavailable_command": "Команда недоступна в этом проекте",
    "start_failed": "Команду не удалось подготовить",
    "busy": "Консоль занята",
    "not_running": "Job уже не выполняется",
    "unknown_job": "Неизвестная job",
    "invalid_cursor": "Курсор вне вывода job",
    "bad_request": "Некорректный запрос",
}

# The panel, dialog and output strings of the Harness "Commands" panel.
PANEL_LABELS = (
    "Команды",
    "Запустить",
    "Отмена",
    "Отменить job",
    "Подтвердите запуск",
    "Подтвердите отмену job",
    "Отмена останавливает команду; уже внесённые изменения не откатываются.",
    "Введите {word}, чтобы подтвердить",
    "Занято: {command}",
    "Показать вывод",
    "Вывод обрезан",
    "Код возврата: {code}",
    "Выполняется",
    "Завершена",
    "Не удалась",
    "Отменена",
    "Команда недоступна для выбранного проекта",
    "Нужно превью плана очистки: запустите команду из TUI",
    "Загрузка каталога команд…",
    "В этом разделе нет команд",
    "Вывода пока нет",
)


class Runtime:
    port = PORT
    token = TOKEN
    closing = False

    def __init__(self, router: RequestRouter, static_root: Path) -> None:
        self.router = router
        self.static_root = static_root

    def client_opened(self) -> None:
        pass

    def client_closed(self) -> None:
        pass


class Executor:
    """Emits two fragments, then holds the command until the test releases it."""

    def __init__(self) -> None:
        self.release = asyncio.Event()
        self.ran: list[list[str]] = []

    async def __call__(
        self, argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        self.ran.append(list(cast(list[str], argv)))
        emit = cast(Callable[[str, str], None], on_output)
        emit("stdout", "first\n")
        emit("stdout", "second\n")
        await self.release.wait()
        emit("stderr", "third\n")
        return 0


def _catalog() -> dict[str, object]:
    return cast(dict[str, object], json.loads(web_catalog.render()))


def _english(text: str) -> str:
    english = cast(dict[str, str], _catalog()["en"]).get(text, "")
    assert english and english != text, text
    return english


async def _ask(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
    await socket.send_text(json.dumps(request))
    return cast(dict[str, object], json.loads(await socket.receive_text()))


def test_a_browser_lists_starts_confirms_and_resumes_a_job_over_the_websocket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal: list[dict[str, object]] = []
    # The real journal resolves Git; the record it would write is kept in memory.
    monkeypatch.setattr(
        command_journal, "append", lambda repo, record: journal.append(dict(record))
    )

    async def scenario() -> None:
        executor = Executor()
        parts = composition.compose(
            tmp_path,
            snapshots=cast(SnapshotService, object()),
            jobs=composition.job_service(tmp_path, executor=executor),
            decisions=cast(DecisionService, object()),
            events=cast(OrchestrationEvents, object()),
            screens=cast(ScreenService, object()),
        )
        runtime = Runtime(parts.router, tmp_path / "no-build")
        headers = [
            (b"host", f"127.0.0.1:{PORT}".encode()),
            (b"origin", f"http://127.0.0.1:{PORT}".encode()),
            (b"cookie", cookie_name(PORT) + b"=" + TOKEN.encode()),
        ]
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN, headers=headers) as ws:
            listed = await _ask(ws, {"id": 1, "type": "job.catalog", "section": "harness"})
            assert listed["ok"] is True
            commands = cast(list[dict[str, object]], listed["commands"])
            by_key = {command["command_id"]: command for command in commands}
            uninstall = by_key["uninstall-apply"]
            assert uninstall["typed_confirmation"] == "UNINSTALL"

            # Without the typed word the server refuses, whatever the client claims.
            refused = await _ask(
                ws,
                {
                    "id": 2,
                    "type": "job.start",
                    "command_id": "uninstall-apply",
                    "confirmed": True,
                    "client": "browser",
                },
            )
            assert refused["ok"] is False and executor.ran == []
            assert cast(dict[str, object], refused["error"])["code"] == (
                "confirmation_required"
            )

            started = await _ask(
                ws,
                {
                    "id": 3,
                    "type": "job.start",
                    "command_id": "uninstall-apply",
                    "confirmed": True,
                    "confirmation": "UNINSTALL",
                    "client": "browser",
                },
            )
            assert started["ok"] is True, started
            job = cast(dict[str, object], started["job"])
            assert job["mutating"] is True and job["phase"] == "running"
            assert job["command_id"] == "uninstall-apply"
            job_id = job["id"]

            # A second mutation is busy and names the running job.
            busy = await _ask(
                ws,
                {
                    "id": 4,
                    "type": "job.start",
                    "command_id": "registry",
                    "client": "browser",
                },
            )
            busy_error = cast(dict[str, object], busy["error"])
            assert (busy_error["code"], busy_error["job_id"]) == ("busy", job_id)
            jobs = await _ask(ws, {"id": 5, "type": "job.list"})
            [summary] = cast(list[dict[str, object]], jobs["jobs"])
            assert (summary["id"], summary["mutating"]) == (job_id, True)

            # A resumed subscription from the first fragment replays only what follows it.
            await ws.send_text(
                json.dumps(
                    {"id": 6, "type": "job.subscribe", "job_id": job_id, "cursor": 1}
                )
            )
            first = json.loads(await ws.receive_text())
            assert [part["text"] for part in first["job"]["output"]] == ["second\n"]
            assert first["job"]["cursor"] == 2 and first["job"]["done"] is False
            executor.release.set()
            output: list[dict[str, str]] = []
            while True:
                reply = json.loads(await ws.receive_text())
                assert reply["id"] == 6
                output += reply["job"]["output"]
                if reply["job"]["done"]:
                    break
            assert output == [{"channel": "stderr", "text": "third\n"}]
            assert reply["job"]["phase"] == "completed"
            assert reply["job"]["returncode"] == 0 and reply["job"]["cursor"] == 3

    asyncio.run(scenario())
    assert journal[0]["client"] == "browser"
    assert journal[0]["command_id"] == "uninstall-apply"


def test_every_listed_command_class_and_refusal_has_its_ru_and_en_labels(
    tmp_path: Path,
) -> None:
    async def idle(argv: object, *, cwd: Path, on_output: object, cancel_event: object) -> int:
        return 0

    served = composition.job_service(tmp_path, executor=idle)
    for section in ("harness", "diagnostics"):
        for command in served.commands(section):
            _english(str(command["title"]))
    for reversibility, reason in CONFIRMATION_REASONS.items():
        _english(reason)
        _english(REVERSIBILITY_LABELS[reversibility])
    assert set(JOB_ERROR_LABELS) == set(_ERRORS) | {"bad_request"}
    for label in JOB_ERROR_LABELS.values():
        _english(label)
    for label in PANEL_LABELS:
        _english(label)
    assert _english(
        "Отмена останавливает команду; уже внесённые изменения не откатываются."
    ) == CANCEL_KEEPS_CHANGES
    assert "{word}" in _english("Введите {word}, чтобы подтвердить")
    assert "{command}" in _english("Занято: {command}")
