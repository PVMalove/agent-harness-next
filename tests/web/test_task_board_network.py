"""The web Task Board over the real FastAPI application: the /ws route and its security middleware
driven over ASGI with a fake GitHub runner serve the specs and the board the page parses, and every
label of the board page has its ru/en catalog entry."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from harness.console.backend.api.app import create_app
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
