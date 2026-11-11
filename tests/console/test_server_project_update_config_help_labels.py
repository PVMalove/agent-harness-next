"""The data and the ru/en labels of the web Open Project, Update Harness, Configuration and Help
pages: what a browser reads over the FastAPI /ws route for the fixture project (the four screens,
one file diff and the commands of the job sections `setup`, `update` and `configuration`), the
English text of every Russian label the four routes show, and that no request rebinds the
served project."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import cast

from harness.console.backend import composition
from harness.console.backend.api.app import create_app
from harness.console.backend.api.protocol.screens import SCREEN_TYPES
from harness.console.backend.api.schemas import REPLIES, REQUESTS
from harness.console.backend.application.decisions import DecisionService
from harness.console.backend.application.events import OrchestrationEvents
from harness.console.backend.application.snapshots import SnapshotService
from harness.console.kernel import web_catalog

from ._asgi_ws import AsgiWebSocket
from ._screen_facts import Facts, service
from .test_server_screens import PORT, TOKEN, Runtime, _read
from .test_web_fixture_project_update_config_help import (
    DIFF_PATH,
    DIFF_TEXT,
    FIXTURES,
    configuration,
    open_project,
    update,
)

FRONTEND = (
    Path(__file__).resolve().parents[2] / "harness" / "console" / "frontend" / "src"
)
# The sources of the four routes; every `t("…")` literal in them is a label the routes show.
ROUTE_SOURCES = (
    "routes/OpenProject.tsx",
    "project/format.ts",
    "routes/UpdateHarness.tsx",
    "update/format.ts",
    "routes/Configuration.tsx",
    "configuration/changes.ts",
    "configuration/format.ts",
    "routes/Help.tsx",
    "help/Markdown.tsx",
)
# Labels the routes pass to `t` from a constant rather than a literal.
CONSTANT_LABELS = (
    # Open Project: the stages, the action words and the candidate marks.
    "Выбор проекта",
    "Предварительные проверки",
    "Установка / внедрение",
    "Настройка",
    "Итоговая диагностика",
    "обновление",
    "новая установка",
    "внедрение",
    "Открыт",
    "Не открыт",
    "План появится после проверки пути.",
    # Update Harness: the modes, their consequences, the drift rows and the diff kinds.
    "Обычное",
    "С перезаписью управляемых файлов",
    "С перезаписью выбранных seed-файлов",
    "Локальные правки сохраняются. Остановится на конфликтах.",
    "⚠ Заменит и конфликтные файлы версией пакета: ваши правки в них пропадут.",
    "Только отмеченные seed-файлы; остальное не меняется.",
    "обновятся",
    "добавятся",
    "будут восстановлены",
    "будут убраны",
    "с локальными правками (сохранятся)",
    "в конфликте (нужна перезапись)",
    "конфликт",
    "обновится",
    "добавится",
    "восстановится",
    "удалится",
    "ваши правки",
    "Изменён и у вас, и в пакете: обычное обновление остановится, перезапись заменит файл версией пакета.",
    "Файл будет заменён версией из пакета.",
    "Новый файл пакета: будет добавлен.",
    "Файла нет на диске: он будет восстановлен.",
    "Файла больше нет в пакете: он будет удалён.",
    "Ваши локальные правки: обычное обновление их сохранит.",
    "Seed-файл отличается от шаблона: обновление его не трогает, пока не выбрана перезапись.",
    "Harness не установлен",
    "Отметьте хотя бы один файл",
    # Configuration: the adapter states, the refusals and the tab.
    "актуален",
    "требует обновления",
    "не установлен",
    "Скрытое значение нельзя записать: введите его заново",
    "Сначала установите engineering-suite или backend-orchestration через меню подключения проекта",
    "Незавершённая запись конфигурации: сначала восстановите её",
    "Файл должен быть JSON-объектом",
    "Изменений нет",
    "История",
)
CYRILLIC = re.compile("[а-яА-ЯёЁ]")


class _Facts(Facts):
    """The fixture project behind the screen service."""

    def open_project(self, repo: Path, /) -> dict[str, object]:
        self._count("open_project")
        return open_project().to_payload()

    def update_harness(self, repo: Path, /) -> dict[str, object]:
        self._count("update_harness")
        return update().to_payload()

    def configuration(self, repo: Path, /) -> dict[str, object]:
        self._count("configuration")
        return configuration().to_payload()

    def update_diff(self, repo: Path, relative: str, /) -> str:
        self.diffs.append(relative)
        return DIFF_TEXT


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


def _fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def _reply(socket: AsgiWebSocket, request: dict[str, object]) -> dict[str, object]:
    await socket.send_text(json.dumps({"id": "r", **request}))
    return cast(dict[str, object], json.loads(await socket.receive_text()))


def _served(tmp_path: Path) -> dict[str, object]:
    runtime = _runtime(tmp_path)

    async def scenario() -> dict[str, object]:
        found: dict[str, object] = {}
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            found["open"] = await _read(socket, {"type": "open_project.snapshot"})
            found["update"] = await _read(socket, {"type": "update_harness.snapshot"})
            found["diff"] = await _read(
                socket, {"type": "update_harness.diff", "path": DIFF_PATH}
            )
            found["configuration"] = await _read(
                socket, {"type": "configuration.snapshot"}
            )
            for language in ("ru", "en"):
                found[f"help-{language}"] = await _read(
                    socket, {"type": "help.snapshot", "language": language}
                )
            for section in ("setup", "update", "configuration"):
                found[f"catalog-{section}"] = await _reply(
                    socket, {"type": "job.catalog", "section": section}
                )
            for field in ("project", "repo", "path"):
                found[f"switch-{field}"] = await _reply(
                    socket, {"type": "open_project.snapshot", field: "/work/other"}
                )
            found["help-force"] = await _reply(
                socket, {"type": "help.snapshot", "language": "ru", "force": True}
            )
            found["diff-unlisted"] = await _reply(
                socket, {"type": "update_harness.diff", "path": "../outside.txt"}
            )
        return found

    return asyncio.run(scenario())


def test_the_pages_read_the_fixture_data_over_the_websocket_route(
    tmp_path: Path,
) -> None:
    found = _served(tmp_path)
    assert found["open"] == _fixture("open-project.json")
    assert found["update"] == _fixture("update-harness.json")
    assert found["diff"] == _fixture("update-harness-diff.json")
    assert found["configuration"] == _fixture("configuration.json")
    assert found["help-ru"] == _fixture("help-ru.json")
    assert found["help-en"] == _fixture("help-en.json")
    for section in ("setup", "update", "configuration"):
        catalog = cast(dict[str, object], found[f"catalog-{section}"])
        assert REPLIES.validate_python(catalog).type == "job.catalog"
        served = {
            key: value
            for key, value in catalog.items()
            if key not in {"v", "id", "type", "ok"}
        }
        assert served == _fixture(f"{section}-catalog.json")


def test_no_request_rebinds_the_served_project(tmp_path: Path) -> None:
    found = _served(tmp_path)
    for name in ("switch-project", "switch-repo", "switch-path", "help-force"):
        reply = cast(dict[str, object], found[name])
        assert reply["ok"] is False
        assert cast(dict[str, object], reply["error"])["code"] == "bad_request", name
    unlisted = cast(dict[str, object], found["diff-unlisted"])
    assert unlisted["ok"] is False
    # The request union of the schema: no request carries a project, a repository or a root.
    schema = REQUESTS.json_schema(ref_template="#/$defs/{model}")
    fields = {
        name
        for model in schema.get("$defs", {}).values()
        for name in cast(dict[str, object], model.get("properties", {}))
    }
    assert not fields & {"project", "repo", "repository", "root", "cwd", "workdir"}
    assert not any(
        word in kind for kind in SCREEN_TYPES for word in ("switch", "activate", "bind")
    )


def _catalog_en() -> dict[str, str]:
    return cast(dict[str, str], json.loads(web_catalog.render())["en"])


def _page_labels() -> set[str]:
    labels = set(CONSTANT_LABELS)
    for relative in ROUTE_SOURCES:
        source = (FRONTEND / relative).read_text(encoding="utf-8")
        labels.update(re.findall(r'\bt\("((?:[^"\\]|\\.)+)"', source))
    return {label for label in labels if CYRILLIC.search(label)}


def test_every_russian_label_of_the_four_routes_has_its_english_text() -> None:
    english = _catalog_en()
    labels = _page_labels()
    missing = sorted(label for label in labels if not english.get(label))
    assert missing == []
    untranslated = sorted(label for label in labels if english[label] == label)
    assert untranslated == []
    assert english["Действие"] == "Action"
    assert english["отмечено {ticked} из {total}"] == "{ticked} of {total} ticked"
    # The Help section titles come from the guide in each language, not from the catalog.
    titles = cast(dict[str, list[str]], _fixture("help-facts.json"))
    assert titles["en"][0] == "Console window"
