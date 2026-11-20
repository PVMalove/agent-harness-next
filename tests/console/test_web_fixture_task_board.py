"""The fixture snapshots of the web Task Board page are what `TaskBoardService` serves for synthetic
tracker facts and one in-memory ledger: the specs, a fresh board and the last good board while the
tracker is unavailable. They hold no demo values of the #board mockup, and the page's TTL constant
equals the server's. `python -m tests.console.test_web_fixture_task_board` rewrites them."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from harness.console.backend.application.ports import TrackerUnavailable
from harness.console.backend.application.task_board import TaskBoardService
from harness.console.backend.domain.task_board import (
    BOARD_TTL_SECONDS,
    BlockerFact,
    PullRef,
    SpecList,
    SpecTickets,
    TrackerSpec,
    TrackerTicket,
)
from harness.console.kernel.reports import BatchSummary, LedgerView, StageEntry

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "web" / "fixtures"
TASK_BOARD_TS = (
    ROOT / "harness" / "console" / "frontend" / "src" / "ws" / "taskBoard.ts"
)
ISSUES = "https://tracker.example.test/acme/app/issues/"
# Values of the accepted mockup that must never reach the console or its fixtures.
MOCKUP_DEMO = ("862", "912", "gh: authentication required", "2 мин", "PVMalove")

SPEC_BODY = "## Integration Branch\n\n`integration/board-fixture`\n"


def _body(
    what: str,
    criteria: list[str],
    files: list[str] = (),  # type: ignore[assignment]
    blocked: list[str] = (),  # type: ignore[assignment]
    sp: int | None = None,
) -> str:
    parts = [f"## What to build\n\n{what}\n"]
    if sp is not None:
        parts.append(f"## Story Points\n\n{sp}\n")
    parts.append(
        "## Acceptance criteria\n" + "".join(f"- [ ] {item}\n" for item in criteria)
    )
    if files:
        parts.append(
            "## Relevant Files (Discovery Context)\n"
            + "".join(f"- {item}\n" for item in files)
        )
    if blocked:
        parts.append("## Blocked by\n" + "".join(f"- {item}\n" for item in blocked))
    return "\n".join(parts)


def _ticket(
    n: int,
    title: str,
    labels: tuple[str, ...],
    body: str,
    *,
    closed: bool = False,
    url: str | None = None,
    pr: PullRef | None = None,
    native: tuple[BlockerFact, ...] = (),
) -> TrackerTicket:
    return TrackerTicket(
        f"#{n}",
        n,
        title,
        url if url is not None else f"{ISSUES}{n}",
        closed,
        labels,
        body,
        native,
        pr,
    )


SPEC = TrackerSpec(
    "#501",
    501,
    "Синтетическая спека доски",
    f"{ISSUES}501",
    SPEC_BODY,
    7,
    6,
)
OTHER_SPEC = TrackerSpec(
    "#502", 502, "Вторая синтетическая спека", None, "", None, None
)

TICKETS = (
    _ticket(
        511,
        "Экран списка задач",
        ("afk", "status::blocked", "priority::p1"),
        _body(
            "Показать список задач спеки.\nВторая строка описания.",
            ["Список открывается", "Пустой список подписан"],
            ["`harness/console/` — консоль"],
            ["Blocked by #512 — нужен источник"],
            sp=3,
        ),
    ),
    _ticket(
        512,
        "Источник данных доски",
        ("afk", "status::ready", "priority::p0"),
        _body(
            "Читать снимок трекера.",
            ["Снимок читается", "Ошибка трекера видна", "TTL соблюдается"],
            ["`harness/console/backend/` — сервер", "docs/board.md - заметки"],
            sp=5,
        ),
    ),
    _ticket(
        513,
        "Фильтры доски",
        ("afk", "pipeline::fast", "status::in-progress", "priority::p2"),
        _body("Поиск и приоритет.", ["Фильтр сужает карточки"], sp=2),
    ),
    _ticket(
        514,
        "Модальное окно тикета",
        ("hitl", "status::in-progress"),
        _body("Вкладки и копирование.", ["Вкладки переключаются"], sp=3),
        pr=PullRef("#520", "https://tracker.example.test/acme/app/pull/520"),
    ),
    _ticket(
        515,
        "Каркас страницы",
        ("afk", "status::in-progress"),
        _body("Маршрут в AppShell.", ["Маршрут открывается"], sp=1),
        closed=True,
    ),
    _ticket(
        516,
        "<script>alert(1)</script> Небезопасный заголовок",
        ("afk", "status::blocked"),
        _body(
            "<img src=x onerror=alert(1)> **жирный** текст",
            ["<b>не HTML</b>", "`код` и [ссылка](javascript:alert(1))"],
            blocked=["Blocked by #599 — внешний тикет"],
        ),
        url="javascript:alert(1)",
    ),
    _ticket(
        517,
        "Счётчики колонок",
        ("afk", "status::ready", "priority::p1"),
        _body("Счётчики из снимка.", ["Счётчик равен снимку"]),
    ),
)
BLOCKER_STATES = {"#512": False}


def _ledger(repo: Path) -> LedgerView:
    at = "2026-11-09T0{}:00:00Z"
    return LedgerView(
        batches=[
            BatchSummary("b-513", "#513", "active", at.format(1)),
            BatchSummary("b-514", "#514", "active", at.format(1)),
        ],
        stages=[
            StageEntry("d-513", "b-513", "#513", "developer", "working", at.format(2)),
            StageEntry(
                "d-514", "b-514", "#514", "code-review", "working", at.format(3)
            ),
        ],
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


class _Reader:
    def __init__(self) -> None:
        self.failure: TrackerUnavailable | None = None

    def tracker_type(self, repo: Path) -> str:
        return "github"

    def specs(self, repo: Path) -> SpecList:
        return SpecList((SPEC, OTHER_SPEC))

    def board(self, repo: Path, spec_ref: str) -> SpecTickets:
        if self.failure is not None:
            raise self.failure
        return SpecTickets(SPEC, TICKETS, BLOCKER_STATES)


def fixtures() -> dict[str, object]:
    clock, reader = _Clock(), _Reader()
    service = TaskBoardService(
        Path("/nonexistent-board-repo"), clock=clock, reader=reader, ledger=_ledger
    )

    async def serve() -> dict[str, object]:
        specs = await service.specs()
        board = await service.board("#501")
        clock.now += 95.0
        reader.failure = TrackerUnavailable("auth", "tracker login required")
        stale = await service.board("#501")
        return {
            "task-board-specs.json": specs.payload,
            "task-board.json": board.payload,
            "task-board-stale.json": stale.payload,
        }

    return asyncio.run(serve())


def _text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_every_committed_fixture_equals_the_served_snapshot() -> None:
    for name, value in fixtures().items():
        assert (FIXTURES / name).read_text(encoding="utf-8") == _text(
            value
        ), f"{name} drifted: python -m tests.console.test_web_fixture_task_board"


def test_the_fixtures_cover_every_column_and_the_stale_board() -> None:
    rendered = fixtures()
    board = rendered["task-board.json"]
    assert isinstance(board, dict)
    assert [column["count"] for column in board["columns"]] == [2, 2, 1, 1, 1]
    assert board["stale"] is None and board["ledger"] == "ok"
    stale = rendered["task-board-stale.json"]
    assert isinstance(stale, dict)
    assert stale["stale"] == {"reason": "auth", "message": "tracker login required"}
    assert stale["age_seconds"] == 95.0
    assert stale["tickets"] == board["tickets"]


def test_the_fixtures_hold_no_mockup_demo_values() -> None:
    for name in fixtures():
        text = (FIXTURES / name).read_text(encoding="utf-8")
        assert [value for value in MOCKUP_DEMO if value in text] == [], name


def test_the_page_ttl_is_the_server_ttl() -> None:
    found = re.search(
        r"export const BOARD_TTL_MS = (\d+);", TASK_BOARD_TS.read_text(encoding="utf-8")
    )
    assert found is not None
    assert int(found.group(1)) == int(BOARD_TTL_SECONDS * 1000)


def main() -> None:
    for name, value in fixtures().items():
        (FIXTURES / name).write_text(_text(value), encoding="utf-8")


if __name__ == "__main__":
    main()
