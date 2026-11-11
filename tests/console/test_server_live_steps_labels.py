"""The ru/en labels of the live step list: the steps a browser receives over the FastAPI /ws route
name a structure and event types, and every label the web route shows for them, and for the
page itself, has its English text in the web catalog."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast, get_args

from harness.console.backend.api import schemas
from harness.console.backend.api.app import create_app
from harness.console.kernel import web_catalog

from ._asgi_ws import AsgiWebSocket
from .test_server_live_steps import PORT, TOKEN, Reader, _project, _runtime

# What the route shows for a step's structure (`ws/steps.ts`, `STRUCTURE_LABELS`).
STRUCTURE_LABELS = {
    "available": "структура доступна",
    "unavailable": "структура недоступна",
}
# The text of each orchestration event (`ws/steps.ts`, `EVENT_LABELS`).
EVENT_LABELS = {
    "batch.transition": "Пакет {batch}: {from} → {to}",
    "dispatch.transition": "Dispatch {dispatch}: {from} → {to}",
    "gate.decision": "Гейт {dispatch}: {decision}",
    "qa.run": "Прогон QA {dispatch}: {outcome}",
    "qa.attempt": "Попытка QA {dispatch} не прошла этап {stage}",
}
# The page strings of the "Ход работы" route.
PAGE_LABELS = (
    "Наблюдаемые шаги, роли и события. Внутренние рассуждения не отображаются.",
    "Источники шагов",
    "наблюдаемые данные",
    "Шаги, роли и инструменты приходят структурированными.",
    "Только plain-хвост лога. Не выдаём его за шаги и не показываем thinking.",
    "Сессии",
    "Все сессии",
    "{shown} из {total}",
    "Все роли",
    "Фильтр по роли",
    "Только наблюдаемые события; отсутствие события не доказывает остановку.",
    "Шаги и события",
    "наблюдаемые факты",
    "Шагов пока нет",
    "Сессий пока нет",
    "Источник оркестрации недоступен",
    "дальше: {role}",
)


def _english(text: str) -> str:
    catalog = cast(dict[str, dict[str, str]], json.loads(web_catalog.render()))
    english = catalog["en"].get(text, "")
    assert english and english != text, text
    return english


def test_the_steps_a_browser_receives_have_ru_and_en_labels(tmp_path: Path) -> None:
    _project(tmp_path)
    runtime = _runtime(tmp_path, Reader())

    async def scenario() -> list[dict[str, object]]:
        steps: list[dict[str, object]] = []
        async with AsgiWebSocket(create_app(runtime), PORT, TOKEN) as socket:
            await socket.send_text(json.dumps({"id": 1, "type": "steps.subscribe"}))
            sources: set[object] = set()
            while sources != {"structured", "plain"}:
                reply = json.loads(await socket.receive_text())
                if reply.get("kind") == "steps":
                    steps.extend(reply["steps"])
                    sources |= {step.get("source") for step in reply["steps"]}
        return steps

    steps = asyncio.run(scenario())

    structures = {step["structure"] for step in steps if step["origin"] == "agent"}
    assert structures == {"available", "unavailable"}
    for structure in structures:
        _english(STRUCTURE_LABELS[cast(str, structure)])
    assert _english("структура недоступна") == "structure unavailable"


def test_every_event_type_and_page_string_has_its_english_text() -> None:
    event = schemas.OrchestrationStep.model_fields["event"].annotation
    assert set(EVENT_LABELS) == set(get_args(event))
    for template in EVENT_LABELS.values():
        english = _english(template)
        for name in ("batch", "dispatch", "from", "to", "decision", "outcome", "stage"):
            assert (f"{{{name}}}" in template) == (f"{{{name}}}" in english), template
    for label in PAGE_LABELS:
        _english(label)
    assert "{shown}" in _english("{shown} из {total}")
