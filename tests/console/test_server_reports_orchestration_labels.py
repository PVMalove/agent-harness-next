"""The data and the ru/en labels of the web Reports, Orchestration, Recovery and Container route
pages: what a browser reads over the FastAPI /ws route for the fixture ledger and core answers
(the four screens, a report body, a batch chronology and the commands of the job section
`recovery`), and the English text of every Russian label the four routes show."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.schemas import REPLIES
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel import web_catalog
from harness.console.kernel.batch_history import History
from harness.console.kernel.container_route import Authored
from harness.console.kernel.coordinator_api import ApiResult
from harness.console.kernel.coordinator_catalog import _COORDINATOR_SCRIPT
from harness.console.kernel.pipeline_kpi import (
    pipeline_analytics_from_payload,
    pipeline_kpi_from_payload,
)
from harness.console.kernel.reports import LedgerView, ledger_from_payload

from ._asgi_ws import AsgiWebSocket
from ._screen_facts import Facts, service
from .test_server_screens import PORT, TOKEN, Runtime, _read
from .test_web_fixture_reports_orchestration import (
    FIXTURES,
    LOCK,
    FixtureGit,
    QA_BODY,
    ledger,
    recovery_inputs,
    route_inputs,
)

FRONTEND = (
    Path(__file__).resolve().parents[2] / "harness" / "console" / "frontend" / "src"
)
# The sources of the four routes; every `t("…")` literal in them is a label the routes show.
ROUTE_SOURCES = (
    "routes/Reports.tsx",
    "reports/format.ts",
    "reports/StageList.tsx",
    "reports/ReportDetail.tsx",
    "reports/Timeline.tsx",
    "reports/QaLogs.tsx",
    "routes/Orchestration.tsx",
    "orchestration/format.ts",
    "orchestration/OrchViews.tsx",
    "orchestration/TabExtras.tsx",
    "orchestration/Charts.tsx",
    "orchestration/BatchHistory.tsx",
    "routes/Recovery.tsx",
    "routes/ContainerRoute.tsx",
    "views/RowList.tsx",
)
# Labels the routes pass to `t` from a constant rather than a literal.
CONSTANT_LABELS = (
    "тикет",
    "роль",
    "дата (2026-09-27)",
    "статус стадии",
    "Поток работ",
    "Качество",
    "Гейты",
    "запланирован",
    "ждёт подтверждения",
    "в работе",
    "заблокирован",
    "завершён",
    "провален",
    "не требуется",
    "отменён",
    "Записать нормализацию",
    "Запись пойдёт через транзакцию конфигурации: проверка устаревания, резервная копия.",
    "Выход с сохранением не отменяет batch, не останавливает worker и не очищает worktree.",
    "Действие доступно только в TUI: команда не входит в каталог job сервера",
    "Запусков (batch)",
    "По состояниям",
    "Диспатчи по ролям",
    "Отчёты по итогам",
    "QA-прогонов",
    "Период",
    "начало: неизвестно",
)
CYRILLIC = re.compile("[а-яА-ЯёЁ]")
# A group that names one diagnostic carries its number and code: dynamic, not a fixed label.
DYNAMIC_GROUP = re.compile(r"^Диагностика \d+: ")


class _Facts(Facts):
    """The fixture ledger, lock and core answers behind the screen service."""

    def ledger(self, repo: Path, /) -> LedgerView:
        self._count("ledger")
        return ledger()

    def lock(self, repo: Path, /) -> dict[str, object]:
        self._count("lock")
        return LOCK

    def history(self, repo: Path) -> History:
        self._count("history")
        return recovery_inputs()[0]

    def status(self, repo: Path, batch: str, skip: Sequence[str]) -> ApiResult:
        self.statuses.append((batch, tuple(skip)))
        return recovery_inputs()[1]

    def authored(self, repo: Path) -> Authored:
        return route_inputs()[0]

    def preflight(self, repo: Path, batch: str, role: str, runtime: str) -> ApiResult:
        self.preflights.append((batch, role, runtime))
        return route_inputs()[1]


async def _idle(
    argv: object, *, cwd: Path, on_output: object, cancel_event: object
) -> int:
    return 0


def _runtime(tmp_path: Path) -> Runtime:
    script = tmp_path / _COORDINATOR_SCRIPT
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    parts = composition.compose(
        tmp_path,
        snapshots=cast(SnapshotService, object()),
        jobs=composition.job_service(tmp_path, executor=_idle),
        decisions=cast(DecisionService, object()),
        events=cast(OrchestrationEvents, object()),
        screens=service(_Facts(), publish_git=FixtureGit()),
    )
    return Runtime(parts.router, tmp_path / "no-build")


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _served(tmp_path: Path) -> dict[str, object]:
    runtime = _runtime(tmp_path)

    async def scenario() -> dict[str, object]:
        found: dict[str, object] = {}
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found["reports"] = await _read(socket, {"type": "reports.snapshot"})
            found["report"] = await _read(
                socket, {"type": "reports.report", "dispatch_id": "d-qa"}
            )
            found["timeline"] = await _read(
                socket, {"type": "reports.timeline", "batch_id": "b-887"}
            )
            found["orchestration"] = await _read(
                socket, {"type": "orchestration.snapshot"}
            )
            found["recovery"] = await _read(
                socket, {"type": "recovery.view", "batch": "b-887"}
            )
            found["route"] = await _read(
                socket,
                {"type": "container_route.view", "batch": "b-887", "role": "developer"},
            )
            await socket.send_text(
                json.dumps({"id": "c", "type": "job.catalog", "section": "recovery"})
            )
            found["catalog"] = json.loads(await socket.receive_text())
        return found

    return asyncio.run(scenario())


def test_the_pages_read_the_fixture_data_over_the_websocket_route(
    tmp_path: Path,
) -> None:
    found = _served(tmp_path)
    assert found["reports"] == _fixture("reports.json")
    assert found["report"] == QA_BODY == _fixture("reports-report.json")
    assert found["timeline"] == _fixture("reports-timeline.json")
    orchestration = found["orchestration"]
    assert isinstance(orchestration, dict)
    fixture = _fixture("orch-snapshot.json")
    assert isinstance(fixture, dict)
    # The ledger and the lock are the fixture's; the KPIs are computed at the time of the read.
    assert orchestration["ledger"] == fixture["ledger"]
    assert orchestration["lock"] == {"lock": LOCK, "error": None}
    pipeline_kpi_from_payload(orchestration["kpi"])
    pipeline_analytics_from_payload(orchestration["analytics"])
    assert ledger_from_payload(orchestration["ledger"]).batches[0].batch_id == "b-887"
    assert found["recovery"] == _fixture("recovery.json")
    assert found["route"] == _fixture("container-route.json")
    catalog = found["catalog"]
    assert isinstance(catalog, dict)
    assert REPLIES.validate_python(catalog).type == "job.catalog"
    served = {
        key: value
        for key, value in catalog.items()
        if key not in {"v", "id", "type", "ok"}
    }
    assert served == _fixture("recovery-catalog.json")


def _catalog_en() -> dict[str, str]:
    return cast(dict[str, str], json.loads(web_catalog.render())["en"])


def _page_labels() -> set[str]:
    labels = set(CONSTANT_LABELS)
    for relative in ROUTE_SOURCES:
        source = (FRONTEND / relative).read_text(encoding="utf-8")
        labels.update(re.findall(r'\bt\("((?:[^"\\]|\\.)+)"', source))
    return {label for label in labels if CYRILLIC.search(label)}


def _view_labels(view: dict[str, object]) -> set[str]:
    labels: set[str] = set()
    for row in cast(list[dict[str, str]], view["rows"]):
        labels.update({row["label"], row["mark"]})
        if not DYNAMIC_GROUP.match(row["group"]):
            labels.add(row["group"])
    for action in cast(list[dict[str, object]], view["actions"]):
        labels.add(str(action["label"]))
    labels.update(cast(list[str], view["notes"]))
    return labels


def _kernel_labels(found: dict[str, object]) -> set[str]:
    recovery = cast(dict[str, object], found["recovery"])
    route = cast(dict[str, object], found["route"])
    labels = _view_labels(cast(dict[str, object], recovery["view"]))
    entry = cast(dict[str, str], recovery["entry"])
    labels.add(entry["mark"])
    for tab in cast(list[dict[str, str]], route["tabs"]):
        labels.update({tab["title"], tab["mark"]})
    for label, _ in cast(list[list[str]], route["context"]):
        labels.add(label)
    for stage in cast(dict[str, dict[str, object]], route["stages"]).values():
        labels |= _view_labels(stage)
    return {label for label in labels if label and CYRILLIC.search(label)}


def test_every_russian_label_of_the_four_routes_has_its_english_text(
    tmp_path: Path,
) -> None:
    english = _catalog_en()
    labels = _page_labels() | _kernel_labels(_served(tmp_path))
    missing = sorted(label for label in labels if not english.get(label))
    assert missing == []
    untranslated = sorted(label for label in labels if english[label] == label)
    assert untranslated == []
    assert english["Восстановление batch"] == "Batch recovery"
    assert english[
        "Действие доступно только в TUI: команда не входит в каталог job сервера"
    ] == ("Available in the TUI only: the command is not in the server job catalog")
