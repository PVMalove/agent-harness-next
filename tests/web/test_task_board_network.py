"""The web Task Board over the real FastAPI application: the /ws route and its security middleware
driven over ASGI with a fake GitHub runner serve the specs and the board the page parses, the status
change runs as a confirmed mutating job, and every label of the board page has its ru/en catalog
entry."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

import pytest

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.infrastructure import command_journal
from harness.console.kernel import web_catalog
from tests.console._asgi_ws import AsgiWebSocket
from tests.console.test_server_screens import PORT, TOKEN
from tests.console.test_server_task_board import Tracker, _cards, _read, _runtime

FRONTEND = (
    Path(__file__).resolve().parents[2] / "harness" / "console" / "frontend" / "src"
)

# Every Russian label of the board page, its cards and the ticket modal.
BOARD_LABELS = (
    "Одна доска на спеку. Колонки, блокеры и переносы соответствуют трекеру.",
    "Обновить",
    "Спека",
    "Выбрать спеку",
    "{count} задач",
    "{total} задач · {open} открыто",
    "Открыто",
    "из {total} задач",
    "С блокерами",
    "нельзя перенести",
    "Активный batch",
    "занято",
    "Снимок",
    "обновлено",
    "трекер недоступен",
    "Трекер недоступен.",
    "Показан снимок {age} назад.",
    "Снимка доски ещё нет.",
    "Найти задачу",
    "Поиск задач",
    "Приоритет",
    "Все приоритеты",
    "Без блокеров",
    "Сбросить",
    "{shown} из {total}",
    "Бэклог",
    "blocked / без статуса",
    "Готово к работе",
    "В работе",
    "Review / QA",
    "dispatch или PR",
    "Готово",
    "закрыт после merge",
    "пусто",
    "dispatch: {role}",
    "блокеров: {count}",
    "без блокеров",
    "критериев: {count}",
    "Открыть",
    "нет данных",
    "Спек пока нет",
    "На доске нет задач",
    "Обновление доски",
    "Снимка доски ещё нет",
    "Доска появится, когда трекер снова ответит.",
    "Доска не построена",
    "{n} с",
    "{n} мин",
    "{n} ч",
    "Трекер не настроен",
    "CLI трекера не установлен",
    "Трекер не ответил вовремя",
    "Нет доступа к трекеру",
    "Трекер вернул ошибку",
    "Трекер вернул непонятный ответ",
    "Трекер не нашёл данные",
    "Закрыть",
    "Контекст",
    "Acceptance ({count})",
    "Промпт",
    "Копировать",
    "Текущий статус",
    "Промпт скопирован",
    "Критерии скопированы",
    "Скопируйте текст вручную",
    "Блокеры",
    "Блокеров нет.",
    "Файлы не указаны.",
    # The status change: the select, the confirmation and the refusal captions.
    "Сменить статус",
    "СМЕНА СТАТУСА",
    "Сервер запустит смену метки в {tracker} как мутирующий job и обновит доску.",
    "локальном трекере",
    "Отмена",
    "Смена статуса…",
    "{ticket}: статус обновлён",
    "{ticket} → «{column}»: {reason}",
    "Открыты блокеры: {list}",
    "Активный batch {batch}",
    "Занято: {command}",
    "Ошибка записи в трекер: изменение не сохранено",
    "Трекер недоступен: смена статуса не записана",
    "«Review / QA» вычисляют dispatch и PR; карточку туда не переносят",
    "«Готово» заполняет закрытие тикета после подтверждённого merge",
    "Закрытый тикет не переносится",
    "У тикета активный batch или PR",
    "Переход идёт через «Готово к работе»",
    "Тикет не найден в спеке",
    "Леджер оркестрации недоступен: перенос не записан",
    "Смена статуса не выполнена",
)
# Labels whose English text is the same words.
SAME_IN_ENGLISH = {"Review / QA", "Acceptance ({count})", "dispatch: {role}"}


def test_the_app_serves_the_specs_and_the_board_the_page_reads(tmp_path: Path) -> None:
    tracker = Tracker()
    runtime = _runtime(tmp_path, tracker)

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            # The page's own request bodies: `force` always, the spec as a field.
            reply, specs = await _read(
                socket, {"type": "task_board.specs", "force": False}
            )
            assert reply["type"] == "task_board.specs"
            assert isinstance(reply["cached"], bool)
            listed = cast(list[dict[str, object]], specs["specs"])
            assert [spec["id"] for spec in listed] == ["#862"]
            assert specs["stale"] is None
            reply, board = await _read(
                socket,
                {"type": "task_board.snapshot", "spec": "#862", "force": True},
            )
            assert reply["type"] == "task_board.snapshot"
            assert board["ledger"] == "ok" and board["stale"] is None
            columns = cast(list[dict[str, object]], board["columns"])
            assert [column["id"] for column in columns] == [
                "backlog",
                "ready",
                "progress",
                "review",
                "done",
            ]
            cards = _cards(board)
            assert [column["count"] for column in columns] == [
                sum(card["column"] == column["id"] for card in cards.values())
                for column in columns
            ]
            assert cards["#905"]["dispatch"] == "code-review"
            kpis = cast(dict[str, int], board["kpis"])
            assert kpis["total"] == len(cards)
            tracker.failing = True
            _, stale = await _read(
                socket,
                {"type": "task_board.snapshot", "spec": "#862", "force": True},
            )
            assert cast(dict[str, str], stale["stale"])["reason"] == "auth"
            assert _cards(stale) == cards

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))


def test_every_board_label_has_its_ru_en_catalog_entry() -> None:
    english = json.loads(web_catalog.render())["en"]
    missing = [label for label in BOARD_LABELS if label not in english]
    assert missing == []
    untranslated = [
        label
        for label in BOARD_LABELS
        if english[label] == label and label not in SAME_IN_ENGLISH
    ]
    assert untranslated == []
    assert english["Бэклог"] == "Backlog"
    assert english["нет данных"] == "no data"


def test_every_board_label_is_one_the_page_uses() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            FRONTEND / "routes" / "TaskBoard.tsx",
            *sorted((FRONTEND / "board").glob("*.ts*")),
        ]
    )
    assert [label for label in BOARD_LABELS if f'"{label}"' not in sources] == []


RESULT: dict[str, object] = {
    "ticket": "#903",
    "from": "ready",
    "to": "progress",
    "result": "changed",
    "reason": None,
    "blockers": [],
    "batch": None,
    "message": "status::ready -> status::in-progress",
}


def test_the_status_change_data_and_job_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(command_journal, "append", lambda *args, **kwargs: None)
    executed: list[list[str]] = []
    release = threading.Event()

    async def executor(
        argv: Sequence[str],
        *,
        cwd: Path,
        on_output: Callable[[str, str], None],
        cancel_event: threading.Event,
    ) -> int:
        executed.append(list(argv))
        if "memory" in argv:
            await asyncio.to_thread(release.wait, 10)
            return 0
        on_output("stdout", json.dumps(RESULT) + "\n")
        return 0

    tracker = Tracker()
    jobs = composition.job_service(tmp_path, executor=executor)
    runtime = _runtime(tmp_path, tracker, jobs)

    async def send(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
        await socket.send_text(json.dumps(request))
        reply = json.loads(await socket.receive_text())
        assert isinstance(reply, dict)
        return reply

    async def scenario() -> None:
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            _, board = await _read(socket, {"type": "task_board.snapshot", "spec": "#862"})
            moves = {
                ref: {move["to"]: move for move in cast(list[dict[str, object]], card["moves"])}
                for ref, card in _cards(board).items()
            }
            assert moves["#903"]["progress"]["allowed"] is True
            assert moves["#901"]["ready"] == {
                "to": "ready", "allowed": False, "reason": "open_blockers",
                "blockers": ["#903"], "batch": None,
            }  # fmt: skip
            assert moves["#904"]["ready"]["reason"] == "active_batch"
            assert moves["#904"]["ready"]["batch"] == "b-904"
            start: dict[str, object] = {
                "id": "move",
                "type": "job.start",
                "command_id": "board-status",
                "values": {"spec": "#862", "ticket": "#903", "to": "progress"},
                "client": "browser",
            }
            refused = await send(socket, start)
            assert refused["ok"] is False
            assert cast(dict[str, str], refused["error"])["code"] == "confirmation_required"
            assert executed == []
            started = await send(socket, {**start, "id": "confirmed", "confirmed": True})
            assert started["ok"] is True
            job = cast(dict[str, object], started["job"])
            assert job["command_id"] == "board-status" and job["mutating"] is True
            while not job["done"]:
                reply = await send(
                    socket, {"id": "follow", "type": "job.subscribe", "job_id": job["id"], "cursor": 0}
                )
                job = cast(dict[str, object], reply["job"])
            output = cast(list[dict[str, str]], job["output"])
            assert json.loads("".join(item["text"] for item in output)) == RESULT
            holder = await send(socket, {"id": "hold", "type": "job.start", "command_id": "memory-build"})
            assert holder["ok"] is True
            busy = await send(socket, {**start, "id": "busy", "confirmed": True})
            error = cast(dict[str, str], busy["error"])
            assert error["code"] == "busy"
            assert error["job_id"] == cast(dict[str, str], holder["job"])["id"]
            release.set()

    asyncio.run(asyncio.wait_for(scenario(), timeout=30))
    assert executed[0][2:] == [
        "ticket-status", str(tmp_path), "--spec", "#862", "--ticket", "#903", "--to", "progress",
    ]  # fmt: skip


def test_the_status_change_captions_have_their_english_text() -> None:
    english = json.loads(web_catalog.render())["en"]
    assert english["Открыты блокеры: {list}"] == "Open blockers: {list}"
    assert english["Активный batch {batch}"] == "Active batch {batch}"
    assert english["Занято: {command}"] == "Busy: {command}"
    assert english["Ошибка записи в трекер: изменение не сохранено"] == (
        "Tracker write error: the change was not saved"
    )
    assert english["СМЕНА СТАТУСА"] == "STATUS CHANGE"
    assert english["Сменить статус тикета"] == "Change the ticket status"
