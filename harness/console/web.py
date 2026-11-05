"""Packaged browser view; facts arrive only through the existing Home WebSocket protocol."""

from __future__ import annotations

from importlib.resources import files

from . import i18n

# These are fixed package resources, never names supplied to a filesystem reader by a client.
ASSETS = {"/static/home.js": ("home.js", "text/javascript; charset=utf-8")}
NAVIGATION = (
    (
        "Обзор",
        (
            ("home", "Home", "home"),
            ("diagnostics", "Diagnostics", "pulse"),
            ("update-harness", "Update Harness", "refresh"),
            ("open-project", "Open project", "folder"),
        ),
    ),
    (
        "Работа",
        (
            ("board", "Доска задач", "board"),
            ("agent-activity", "Ход работы", "activity"),
            ("orchestration", "Orchestration", "orchestration"),
            ("reports", "Reports", "reports"),
            ("publish", "Публикация", "github"),
        ),
    ),
    (
        "Контекст",
        (
            ("harness", "Harness", "harness"),
            ("repo-map", "Repo Map", "map"),
            ("configuration", "Configuration", "settings"),
            ("help", "Help", "help"),
        ),
    ),
)


class WebHome:
    """One escaped template environment per server, loaded without Textual or Rich."""

    def __init__(self) -> None:
        from jinja2 import DictLoader, Environment, select_autoescape

        package = files("harness.console")
        self._package = package
        self._env = Environment(
            loader=DictLoader(
                {
                    name: package.joinpath("templates", name).read_text(
                        encoding="utf-8"
                    )
                    for name in ("shell.html", "home.html")
                }
            ),
            autoescape=select_autoescape(("html",)),
        )

    def render(self, project: str, language: str) -> bytes:
        return (
            self._env.get_template("shell.html")
            .render(
                project=project,
                language=language,
                navigation=NAVIGATION,
                section=lambda key: i18n.section_label(language, key),
                tr=lambda text: i18n.tr(language, text),
                fact=lambda text: i18n.fact_label(language, text),
                unavailable=i18n.tr(language, "Недоступно в текущем снимке"),
                labels={key: i18n.tr(language, value) for key, value in WEB_LABELS.items()},
            )
            .encode("utf-8")
        )

    def asset(self, path: str) -> tuple[bytes, str] | None:
        asset = ASSETS.get(path)
        if asset is None:
            return None
        name, mime = asset
        return self._package.joinpath("static", name).read_bytes(), mime


WEB_LABELS = {
    "empty": "В списке нет проблем; это не подтверждает полноту проверок",
    "checks": "{count} проверок",
    "problems": "Показано {shown} из {total} · Полный каталог проверок недоступен",
    "noMap": "Нет карты для HEAD",
    "online": "Онлайн · обновление только по запросу",
    "offline": "Офлайн · обновление каждые 15 секунд",
    "cached": "Кэш",
    "fresh": "Новый снимок",
    "connected": "Подключено",
    "reconnecting": "Переподключение",
    "unavailable": "Недоступно",
    "serverUnavailable": "Сервер недоступен",
    "waiting": "Ожидание снимка",
    "expand": "Развернуть меню",
    "collapse": "Свернуть меню",
}
