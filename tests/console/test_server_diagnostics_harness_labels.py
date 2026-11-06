"""The data and the ru/en labels of the web Diagnostics and Harness routes: what a browser reads
over the FastAPI /ws route (the paged health report, the Harness overview, the maintenance facts
and the commands of both sections), and the English text of every page, drift, status, group and
reason label the routes show for it."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from harness.cleanup import CleanupPlan, WorktreeFact
from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.schemas import REPLIES
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel import web_catalog
from harness.console.kernel.health_report import report_from_payload
from harness.console.kernel.maintenance import (
    REASONS_RU,
    CleanupSummary,
    MaintenanceView,
    Size,
)
from harness.health.model import CheckResult, Fix, Report
from harness.health.render import GROUP_LABELS_RU
from harness.health.report_json import to_json
from harness.json_types import JsonObject

from ._asgi_ws import AsgiWebSocket
from ._screen_facts import Facts, service
from .test_server_screens import PORT, TOKEN, Runtime, _read

# The drift states harness.overview names and the label each route shows (`harness/format.ts`).
DRIFT_LABELS = {
    "clean": "✔ дрейфа нет",
    "drift": "⚠ дрейф есть",
    "missing": "○ дрейф: нет lock",
    "unknown": "○ дрейф неизвестен",
}
# The status words of the check list and the summary (`diagnostics/CheckList.tsx`).
STATUS_LABELS = {
    "ok": "пройдено",
    "warn": "внимание",
    "fail": "ошибки",
    "skipped": "пропущено",
}
# The page strings of the Diagnostics route.
DIAGNOSTICS_LABELS = (
    "Отчёт harness health. Команды «Как исправить» консоль не выполняет — запустите их вручную.",
    "Команды «Как исправить» консоль не выполняет — запустите их вручную.",
    "Сводка здоровья",
    "Проверки",
    "Детали проверки",
    "Проверка не выбрана",
    "Выберите строку слева.",
    "Найти проверку",
    "Все",
    "Проблемы",
    "Пройдено",
    "Пропущено",
    "Сбросить",
    "Ничего не найдено",
    "Нет проверок для этого фильтра",
    "Полный отчёт",
    "Как исправить:",
    "Рекомендация отсутствует",
    "Команда",
    "Команда отсутствует — проверьте настройки вручную",
    "Копировать команду",
    "Команда скопирована",
    "Источник",
    "Пропуск не считается успехом. Онлайн-проверки требуют сети и прав.",
    "Исправить",
    "Применённые фиксы:",
    "Исправление не удалось",
    "Отчёт не построен",
    "Отчёт строится…",
    "{count} проверок",
    "групп: {count}",
    "проверено {checked} из {total}",
    "{shown} из {total}",
    "Офлайн",
    "Онлайн",
    "офлайн",
    "онлайн",
    "Проверить",
    "Экспорт",
)
# The page strings of the Harness route.
HARNESS_LABELS = (
    "Установка, использование пайплайна и обслуживание. Команды выполняются как job сервера после подтверждения.",
    "Команды",
    "Установка",
    "Установлено",
    "установлен",
    "не установлен",
    "Пакет",
    "Скилов",
    "Управляемых файлов",
    "Lock обновлён",
    "Оркестрация",
    "✔ подключена",
    "○ не подключена",
    "Дрейф",
    "Харнесс не установлен: нет читаемого .harness/harness.lock.",
    "Состояние харнесса загружается…",
    "○ Состояние харнесса недоступно: ",
    "{count} скилов",
    "{count} управляемых файлов",
    "{count} объектов",
    "Пайплайн",
    "Использование пайплайна",
    "Запусков (batch)",
    "Тикетов",
    "Диспатчей",
    "Отчётов",
    "тикетов {tickets} · диспатчей {dispatches} · отчётов {reports}",
    "недоступно",
    "Обслуживание",
    "Временные файлы",
    "Временных файлов нет",
    "Статистика считается…",
    "Ошибка плана очистки: ",
    "Жёсткий режим: +",
    "файлов",
    "План",
    "Очистить…",
    "Удалить…",
    "можно удалить",
    "Можно удалить",
)

_ROOT = "/work/project/.harness"


def _report() -> Report:
    """A report with a check of every group and every status."""
    statuses = ("ok", "warn", "fail", "skipped")
    return Report(
        1,
        "/work/project",
        False,
        [
            CheckResult(
                f"{group}.check",
                group,
                statuses[index % 4],  # type: ignore[arg-type]
                f"сообщение {group}",
                Fix("Как поправить", "harness update .") if index % 2 else None,
            )
            for index, group in enumerate(GROUP_LABELS_RU)
        ],
        ["Записана .harness/hook-policy.json"],
    )


def _summary(mode: str) -> CleanupSummary:
    plan = cast(
        CleanupPlan,
        {
            "mode": mode,
            "root": _ROOT,
            "min_age_hours": 24,
            "remove": [
                {"kind": "directory", "path": f"{_ROOT}/.sandboxes/runs/tests/a"}
            ],
            "skipped": [
                {"path": f"{_ROOT}/.sandboxes/runs/qa/b", "reason": reason}
                for reason in REASONS_RU
            ],
        },
    )
    return CleanupSummary(plan, {"runs/tests": Size(2048, 3)})


def _maintenance() -> MaintenanceView:
    tree = Path(f"{_ROOT}/.sandboxes/worktrees/issue-1")
    return MaintenanceView(
        _summary("soft"),
        _summary("hard"),
        [
            WorktreeFact(tree, "feature/issue-1", 0, ""),
            WorktreeFact(
                Path(f"{_ROOT}/.sandboxes/worktrees/issue-2"),
                "feature/issue-2",
                2,
                "worktree has uncommitted changes",
            ),
        ],
        "",
        {tree: Size(1536, 4)},
    )


class _Facts(Facts):
    def health(self, repo: Path, online: bool, /) -> JsonObject:
        self._count("health")
        return to_json(_report())

    def maintenance(self, repo: Path, /) -> dict[str, object]:
        self._count("maintenance")
        return {"maintenance": _maintenance().to_payload(), "error": ""}


async def _idle(
    argv: object, *, cwd: Path, on_output: object, cancel_event: object
) -> int:
    return 0


def _runtime(tmp_path: Path) -> Runtime:
    parts = composition.compose(
        tmp_path,
        snapshots=cast(SnapshotService, object()),
        jobs=composition.job_service(tmp_path, executor=_idle),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=service(_Facts()),
    )
    return Runtime(parts.router, tmp_path / "no-build")


def _catalog() -> dict[str, dict[str, object]]:
    return cast(dict[str, dict[str, object]], json.loads(web_catalog.render()))


def _english(text: str) -> str:
    english = cast(dict[str, str], _catalog()["en"]).get(text, "")
    assert english and english != text, text
    return english


def test_the_pages_read_their_data_over_the_websocket_route(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    async def scenario() -> dict[str, object]:
        found: dict[str, object] = {}
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found["diagnostics"] = await _read(socket, {"type": "diagnostics.snapshot"})
            await socket.send_text(json.dumps({"id": "o", "type": "harness.overview"}))
            found["overview"] = json.loads(await socket.receive_text())
            found["maintenance"] = await _read(socket, {"type": "harness.maintenance"})
            for section in ("diagnostics", "harness"):
                await socket.send_text(
                    json.dumps(
                        {"id": section, "type": "job.catalog", "section": section}
                    )
                )
                found[f"catalog:{section}"] = json.loads(await socket.receive_text())
        return found

    found = asyncio.run(scenario())

    # The paged report is the whole health report, longer than one page or not.
    report = report_from_payload(found["diagnostics"])
    assert report == _report()
    overview = found["overview"]
    assert isinstance(overview, dict) and REPLIES.validate_python(overview)
    assert overview["usage"] == {
        "unavailable": None,
        "batches": 1,
        "tickets": 1,
        "dispatches": 1,
        "reports": 1,
    }
    assert (overview["drift"], overview["package_version"]) == ("clean", "1.0.1")
    view = MaintenanceView.from_payload(
        cast(dict[str, object], found["maintenance"])["maintenance"]
    )
    assert view.soft.plan["skipped"] == _maintenance().soft.plan["skipped"]
    commands = {
        section: {
            command["command_id"]: command
            for command in cast(
                list[dict[str, object]],
                cast(dict[str, object], found[f"catalog:{section}"])["commands"],
            )
        }
        for section in ("diagnostics", "harness")
    }
    assert set(commands["diagnostics"]) == {"diagnostics-fix", "diagnostics-online-fix"}
    assert commands["diagnostics"]["diagnostics-fix"]["needs_confirmation"] is False
    assert (
        commands["diagnostics"]["diagnostics-online-fix"]["needs_confirmation"] is True
    )
    # The commands the Harness page asks for exist, bound to a plan where it sends a digest.
    assert commands["harness"]["cleanup-apply"]["plan_required"] is True
    assert commands["harness"]["cleanup-hard-apply"]["plan_required"] is True
    assert commands["harness"]["worktree-remove"]["inputs"] == ["worktree"]

    # Every group, status and reason the pages show for this data has its ru and en label.
    catalog = _catalog()
    groups = cast(dict[str, str], catalog["groups"])
    for check in report.checks:
        assert groups[check.group] == GROUP_LABELS_RU[check.group]
        # A group label may read the same in English ("Repo Map"), but it is in the table.
        assert cast(dict[str, str], catalog["en"]).get(groups[check.group])
        _english(STATUS_LABELS[check.status])
    reasons = cast(dict[str, str], catalog["reasons"])
    shown = [item["reason"] for item in view.soft.plan["skipped"]] + [
        fact.reason for fact in view.worktrees if fact.reason
    ]
    for reason in shown:
        assert reasons[reason] == REASONS_RU[reason] != reason
    assert any(fact.reason == "" for fact in view.worktrees)
    _english("Можно удалить")


def test_every_label_of_both_routes_has_its_english_text() -> None:
    for drift, label in DRIFT_LABELS.items():
        assert _english(label), drift
    for label in (*DIAGNOSTICS_LABELS, *HARNESS_LABELS):
        _english(label)
    sections = cast(dict[str, dict[str, str]], _catalog()["sections"])
    for section in ("Diagnostics", "Harness", "Update Harness"):
        assert sections[section]["ru"] and sections[section]["en"]
