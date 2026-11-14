"""Экран Diagnostics: полный отчёт `harness health` и три действия — «Онлайн» (аналог запуска
`harness health --online`), «Исправить» (аналог запуска `harness health --fix`, применяющий только
фиксеры FIXERS после явного подтверждения) и «Экспорт» (экспорт отчёта в Markdown). Каждое действие
отображает эквивалент команды CLI. Отчёт экран читает у сервера консоли, а фиксы выполняет job
сервера (`apply_health_fixes`); сам экран проверки не запускает, ожидание ответа идёт в фоновом
потоке.

Команды из блока «Как исправить» предназначены для ручного выполнения разработчиком и только отображаются
на экране: они изменяют настройки машины или удаляют данные, что исключено из автоматического применения.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

from rich.text import Text
from textual import events, on
from textual.message import Message
from textual.widget import Widget
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, ListItem, ListView, Static

from ..crumbs import Crumb
from ..shell import (
    SHELL_CSS,
    ConsoleShell,
    JumpLink,
    SectionCard,
    WrappedValue,
    check_route,
)
from ..logtext import colorize_log
from ...kernel import brand, i18n
from ...kernel import data as console_data
from ....health.model import CheckResult, Report
from ....health.render import GROUP_LABELS_RU
from ...kernel.export import MarkdownDocument, MarkdownSection
from ..client import ScreenClient
from ..server_api import apply_health_fixes
from .commands import call_from_worker, short_repo
from .export import EXPORT_BINDING_KEY, export_document

_STATUS_MARKERS = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]", "skipped": "-"}
_APPLY_LABEL = "Исправить"
_CONFIRM_LABEL = "Подтвердить фиксы"
_MANUAL_NOTE = "Команды «Как исправить» консоль не выполняет — запустите их вручную."
_SUBTITLE = "Отчёт harness health. " + _MANUAL_NOTE
_RUNNING = "health выполняется…"


def _now() -> datetime:
    """The clock of the screen (patched in the snapshot generator for stable pictures)."""
    return datetime.now()


def render_report(report: Report) -> str:
    """Формирует текстовое представление отчёта проверок health со статусами и рекомендациями."""
    summary = report.summary()
    lines = [
        f"Итого: ok={summary['ok']} warn={summary['warn']} "
        f"fail={summary['fail']} skipped={summary['skipped']}",
        _MANUAL_NOTE,
        "",
    ]
    for check in report.checks:
        lines.append(f"{_STATUS_MARKERS[check.status]} {check.id}: {check.message}")
        if check.fix is not None:
            lines.append(f"  -> Как исправить: {check.fix.text}")
            if check.fix.command:
                lines.append(f"     {check.fix.command}")
    if report.fixes_applied:
        lines.append("")
        lines.append("Применённые фиксы:")
        lines.extend(f"  - {command}" for command in report.fixes_applied)
    return "\n".join(lines)


_FIXED_REPORT_LINES = ("Итого:", "Команды «Как исправить»", "Применённые фиксы:")


def _translated_report(report: Report, language: str) -> str:
    """`render_report` with only its own fixed lines translated; check messages are data."""
    lines = []
    for line in render_report(report).split("\n"):
        if line.startswith(_FIXED_REPORT_LINES):
            line = i18n.tr_text(language, line)
        elif line.startswith("  -> Как исправить:"):
            line = line.replace(
                "Как исправить:", i18n.tr_text(language, "Как исправить:"), 1
            )
        lines.append(line)
    return "\n".join(lines)


_COUNTER = re.compile(r"\b(ok|warn|fail|skipped)=(\d+)")
_CHECK_MARKERS = {"[OK] ": "ok", "[WARN] ": "warn", "[FAIL] ": "fail"}
# The totals line in either language (see `render_report` and its translation): the whole counter
# list is required, so foreign output that merely starts with "Итого:" does not start a report.
_TOTALS = re.compile(r"(Итого|Total): ok=\d+ warn=\d+ fail=\d+ skipped=\d+")


def _icon(status: str, *, muted: bool = False) -> Text:
    """The status symbol; a zero counter is muted, like its number."""
    color = brand.PALETTE["muted"] if muted else brand.STATUS_COLORS[status]
    return Text(f"{brand.STATUS_ICONS[status]} ", style=f"bold {color}")


def _summary_line(line: str) -> Text:
    """The totals line with a status symbol before each counter."""
    styled = colorize_log(line)
    shown = Text()
    position = 0
    for counter in _COUNTER.finditer(line):
        shown.append_text(styled[position : counter.start()])
        shown.append_text(_icon(counter.group(1), muted=counter.group(2) == "0"))
        position = counter.start()
    shown.append_text(styled[position:])
    return shown


def _styled_line(line: str, *, in_report: bool) -> Text:
    for marker, status in _CHECK_MARKERS.items():
        if line.startswith(marker):
            return _icon(status) + colorize_log(line)
    # "- " marks a skipped check only inside a report; elsewhere it is a plain list item.
    if in_report and line.startswith("- "):
        return _icon("skipped") + colorize_log(line)
    return colorize_log(line)


def styled_log(text: str) -> Text:
    """`colorize_log(text)` for a log that may hold a health report: every check status and every
    counter of the report also gets its symbol (a colour is never the only cue). The text itself is
    only prefixed on screen; nothing exported or compared changes."""
    shown = Text()
    in_report = False
    for index, line in enumerate(text.split("\n")):
        if index:
            shown.append("\n")
        if _TOTALS.match(line):
            in_report = True
            shown.append_text(_summary_line(line))
        else:
            shown.append_text(_styled_line(line, in_report=in_report))
    return shown


def _styled_report(report: Report, language: str = "ru") -> Text:
    """The same text as `render_report`, with statuses, counters and remedies coloured on screen
    and every status and counter also marked by its symbol."""
    return styled_log(_translated_report(report, language))


def health_document(report: Report, language: str = "ru") -> MarkdownDocument:
    """Формирует структурированный Markdown-документ отчёта health для экспорта в папку артефактов."""
    return MarkdownDocument(
        title=i18n.tr(language, "Health-отчёт"),
        slug="health-report",
        meta=[
            (i18n.tr(language, "Репозиторий"), report.repo),
            (
                i18n.tr(language, "Онлайн-проверки"),
                i18n.tr(language, "да" if report.online else "нет"),
            ),
        ],
        sections=[
            MarkdownSection(
                i18n.tr(language, "Проверки"),
                _translated_report(report, language),
                preformatted=True,
            )
        ],
    )


class DiagnosticsScreen(ConsoleShell):
    """Экран диагностики состояния репозитория с возможностью запуска онлайн-проверок и применения исправлений."""

    CRUMBS = "Главная › Диагностика"
    SECTION = "Diagnostics"
    NARROW_FOOTER_KEYS = ("escape", "e", "f2")
    AUTO_FOCUS = "#diagnostics-scroll"
    CSS = SHELL_CSS + brand.shell_css("""
    DiagnosticsScreen #diagnostics-scroll { height: 1fr; padding: 0 2; }
    DiagnosticsScreen #diagnostics-heading { height: 1; text-style: bold; }
    DiagnosticsScreen #diagnostics-manual { height: auto; color: $text-muted; }
    DiagnosticsScreen #diagnostics-overview { height: auto; margin-bottom: 1; }
    DiagnosticsScreen #diagnostics-summary { height: 1; }
    DiagnosticsScreen #diagnostics-actions { height: 1; }
    DiagnosticsScreen #diagnostics-actions Button { width: auto; min-width: 10; height: 1; margin-right: 1; }
    DiagnosticsScreen #diagnostics-actions #apply-fixes { width: 21; }
    DiagnosticsScreen #diagnostics-export-hint { width: auto; text-align: right; }
    DiagnosticsScreen .action-cli { height: auto; color: $text-muted; }
    DiagnosticsScreen #diagnostics-report { height: auto; }
    DiagnosticsScreen #diagnostics-confirmation { height: auto; color: $text-muted; }
    DiagnosticsScreen #diagnostics-pair { grid-size: 1; height: auto; }
    DiagnosticsScreen.-wide #diagnostics-pair, DiagnosticsScreen.-spacious #diagnostics-pair { grid-size: 2; grid-columns: 1fr 1fr; grid-rows: auto; grid-gutter: 0 1; }
    DiagnosticsScreen #diagnostics-pair > .section-card { height: 100%; }
    DiagnosticsScreen #diagnostics-filters { height: 1; margin-bottom: 1; }
    DiagnosticsScreen #diagnostics-filters Button { height: 1; min-width: 7; width: auto; margin-right: 1; }
    DiagnosticsScreen #check-list { height: auto; max-height: 22; border: none; padding: 0; background: transparent; }
    DiagnosticsScreen #check-list > ListItem { height: auto; padding: 0 1; border-left: solid transparent; border-bottom: solid $border-subtle; }
    DiagnosticsScreen #check-list > ListItem.-highlight, DiagnosticsScreen #check-list:focus > ListItem.-highlight { background: $selection-background; color: $selection-foreground; border-left: solid $selection-edge; }
    DiagnosticsScreen #check-detail, DiagnosticsScreen #check-remedy { height: auto; }
    DiagnosticsScreen #check-command { height: auto; border: round $border-subtle; padding: 0 1; margin: 1 0; }
    DiagnosticsScreen .check-links { height: 1; }
    DiagnosticsScreen .check-links Button { height: 1; width: auto; min-width: 0; margin-right: 1; }
    DiagnosticsScreen.-narrow #diagnostics-manual, DiagnosticsScreen.-narrow .action-cli { display: none; }
    DiagnosticsScreen.-narrow .context-strip { display: none; }
    """)

    BINDINGS = [Binding(EXPORT_BINDING_KEY, "export", "Экспорт")]

    def __init__(
        self,
        repo: Path,
        *,
        client: ScreenClient,
    ) -> None:
        """Инициализирует экран диагностики репозитория над клиентом сервера консоли."""
        super().__init__()
        self.repo = repo
        self._client = client
        self._report: Report | None = None
        self._confirming_apply = False
        self._generation = 0
        self._cancel = threading.Event()
        self._disposed = False
        self._state = "running"
        self._language = "ru"
        self._filter = "all"
        self._failure = ""
        self._requested_online = False
        self._built_at: datetime | None = None
        self._shown: list[CheckResult] = []
        self._selected: CheckResult | None = None

    def compose_strip(self) -> ComposeResult:
        yield WrappedValue(self._strip_text())
        yield Static("Экспорт — клавиша e", id="diagnostics-export-hint")

    def compose_content(self) -> ComposeResult:
        """Summary, actions, attention cards and all checks in report order."""
        with VerticalScroll(id="diagnostics-scroll"):
            yield Static("Диагностика", id="diagnostics-heading")
            yield Static(_SUBTITLE, id="diagnostics-manual")
            with SectionCard(title="Health-отчёт", id="diagnostics-overview"):
                yield Static("", id="diagnostics-summary", classes="no-i18n")
                with Horizontal(id="diagnostics-actions"):
                    yield Button("Офлайн", id="offline-checks", compact=True)
                    yield Button("Онлайн", id="online-checks", compact=True)
                    yield Button(_APPLY_LABEL, id="apply-fixes", compact=True)
                    yield Button("Экспорт", id="export", compact=True)
                yield Static(
                    "", id="diagnostics-cli", classes="action-cli no-i18n", markup=False
                )
            yield Static(
                _RUNNING, id="diagnostics-report", classes="no-i18n", markup=False
            )
            yield Static(
                "", id="diagnostics-confirmation", classes="no-i18n", markup=False
            )
            with Grid(id="diagnostics-pair"):
                with SectionCard(title="Проверки", id="checks-list-card"):
                    with Horizontal(id="diagnostics-filters"):
                        for status, label in (
                            ("all", "Все"),
                            ("fail", "✖"),
                            ("warn", "⚠"),
                            ("skipped", "○"),
                        ):
                            yield Button(
                                label,
                                id=f"filter-{status}",
                                compact=True,
                                classes="no-i18n",
                            )
                    yield ListView(id="check-list")
                with SectionCard(title="Детали проверки", id="check-detail-card"):
                    yield Static("", id="check-detail", classes="no-i18n", markup=False)
                    yield Static("", id="check-remedy", classes="no-i18n", markup=False)
                    yield Static("", id="check-command", classes="no-i18n", markup=False)
                    with Horizontal(classes="check-links"):
                        yield Button(
                            "Копировать команду", id="copy-check-command", compact=True
                        )
                        yield JumpLink("Diagnostics", id="check-jump")

    def on_mount(self) -> None:
        """Запускает первичное построение отчёта проверок при монтировании экрана."""
        self._language = getattr(self.app, "language", "ru")
        self.app.message_signal.subscribe(self, self._observe_input, immediate=True)
        self._run_health(lambda: self._client.diagnostics())

    def _observe_input(self, message: Message) -> None:
        if not self._confirming_apply:
            return
        button = self._apply_button()
        if isinstance(message, events.Key):
            if message.key in ("enter", "space") and button.has_focus:
                return
            self._reset_apply()
        elif isinstance(message, events.MouseDown):
            if button.region.contains(message.screen_x, message.screen_y):
                return
            self._reset_apply()
        elif isinstance(message, (events.MouseScrollUp, events.MouseScrollDown)):
            self._reset_apply()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Обрабатывает нажатия кнопок экрана (онлайн-проверки, применение фиксов, экспорт)."""
        if event.button.id != "apply-fixes":
            self._reset_apply()
        button_id = event.button.id or ""
        if button_id.startswith("filter-"):
            self._filter = button_id.removeprefix("filter-")
            self._render_groups()
            return
        if button_id == "copy-check-command":
            check = self._selected
            if check is not None and check.fix and check.fix.command:
                self.app.copy_to_clipboard(check.fix.command)
                self.notify(i18n.tr(self._language, "Команда скопирована"))
            return
        if event.button.id == "offline-checks":
            self._reset_apply()
            self._run_health(lambda: self._client.diagnostics(force=True))
        elif event.button.id == "online-checks":
            self._reset_apply()
            self._run_health(
                lambda: self._client.diagnostics(online=True, force=True), online=True
            )
        elif event.button.id == "apply-fixes":
            self._on_apply_fixes_pressed()
        elif event.button.id == "export":
            self.action_export()
        else:
            ConsoleShell.on_button_pressed(self, event)

    async def action_section(self, index: int) -> None:
        self._reset_apply()
        await ConsoleShell.action_section(self, index)

    async def navigate_crumb(self, crumb: Crumb) -> None:
        self._reset_apply()
        await ConsoleShell.navigate_crumb(self, crumb)

    async def action_back(self) -> None:
        self._reset_apply()
        await ConsoleShell.action_back(self)

    def action_export(self) -> None:
        """Выполняет экспорт текущего отчёта health в файл Markdown."""
        self._reset_apply()
        if self._report is None:
            text = (
                "нечего экспортировать: отчёт ещё строится"
                if self._state == "running"
                else "нечего экспортировать: отчёт не построен"
            )
            self.notify(
                i18n.tr(getattr(self.app, "language", "ru"), text), severity="warning"
            )
            return
        export_document(self, self.repo, health_document(self._report, self._language))

    def _on_apply_fixes_pressed(self) -> None:
        """Обрабатывает нажатие кнопки применения фиксов с запросом подтверждения."""
        if self._report is None:
            text = (
                "Исправление недоступно: дождитесь отчёта"
                if self._state == "running"
                else "Исправление недоступно: повторите проверку"
            )
            self.notify(
                i18n.tr(getattr(self.app, "language", "ru"), text), severity="warning"
            )
            return
        if not self._confirming_apply:
            self._confirming_apply = True
            self._apply_button().label = i18n.tr(
                getattr(self.app, "language", "ru"), _CONFIRM_LABEL
            )
            self._render_state()
            return
        self._reset_apply()
        online = self._report.online
        self._run_health(
            lambda: apply_health_fixes(self._client, online=online), online=online
        )

    def _reset_apply(self) -> None:
        """Сбрасывает состояние подтверждения кнопки применения фиксов к исходному."""
        self._confirming_apply = False
        if self.query("#diagnostics-report"):
            self._render_state()
        self._apply_button().label = i18n.tr(
            getattr(self.app, "language", "ru"), _APPLY_LABEL
        )

    def sync_language(self) -> None:
        """Show the finished report in the current language."""
        ConsoleShell.sync_language(self)
        language = getattr(self.app, "language", "ru")
        if language != self._language:
            self._language = language
            self._reset_apply()
        self._render_overview()
        self._render_state()
        self._relabel_groups()

    def on_unmount(self) -> None:
        """Отменяет фоновые воркеры при размонтировании экрана."""
        self._disposed = True
        self._generation += 1
        self._cancel.set()
        self.app.message_signal.unsubscribe(self)
        self.workers.cancel_node(self)

    def _run_health(self, run: Callable[[], Report], *, online: bool = False) -> None:
        """Ждёт ответа сервера консоли в фоновом потоке worker. Новая проверка или уход с экрана
        только отбрасывают ответ: job фикса на сервере продолжается и не отменяется."""
        self._cancel.set()
        self._cancel = cancel = threading.Event()
        self._generation += 1
        generation = self._generation
        self._state = "running"
        self._requested_online = online
        self._report = None
        self._built_at = None
        self._reset_apply()
        self._shown = []
        self._selected = None
        self.query_one("#check-list", ListView).clear()
        self._show_check(None)
        self._render_overview()
        self._render_state()

        def current() -> bool:
            return (
                not (cancel.is_set() or self._disposed)
                and generation == self._generation
                and self.is_mounted
            )

        def publish(report: Report | None, failure: str = "") -> None:
            if current():
                if report is None:
                    self._show_failure(failure)
                else:
                    self._show(report)

        def work() -> None:
            if cancel.is_set():
                return
            report = None
            failure = ""
            try:
                report = run()
            except Exception as exc:
                failure = str(exc) or type(exc).__name__
            if current():
                call_from_worker(self, lambda: publish(report, failure))

        self.run_worker(work, thread=True, exclusive=True, group="diagnostics")

    def _show_failure(self, text: str) -> None:
        """Отображает причину, по которой отчёт health не построен."""
        self._state = "failed"
        self._report = None
        self._built_at = None
        self._failure = text
        self._render_overview()
        self._render_state()

    def _show(self, report: Report) -> None:
        """Publish only actual health facts, with separate cards and complete groups."""
        self._state = "ready"
        self._report = report
        self._built_at = _now()
        self._render_overview()
        self._render_state()
        self._render_groups()

    def _render_state(self) -> None:
        def tr(text: str) -> str:
            return i18n.tr(self._language, text)

        text = Text()
        if self._state == "running":
            text = _icon("skipped", muted=True) + Text(
                tr(_RUNNING) + " " + tr("Сводка и список появятся после завершения."),
                style=brand.PALETTE["muted"],
            )
        elif self._state == "failed":
            text = (
                _icon("fail")
                + Text(
                    tr("health не выполнен:") + " " + self._failure,
                    style=brand.STATUS_COLORS["fail"],
                )
                + Text(
                    "\n"
                    + tr(
                        "Отчёт не построен. Повторить: «Офлайн». Если повторяется — «Справка» (9)."
                    ),
                    style=brand.PALETTE["muted"],
                )
            )
        elif self._report and self._report.fixes_applied:
            text = (
                _icon("ok")
                + Text(tr("Применённые фиксы:") + "\n")
                + Text("\n".join(self._report.fixes_applied))
            )
        confirmation = Text()
        if self._confirming_apply:
            confirmation = _icon("warn") + Text(
                tr(
                    "Применяются только внутренние фиксы. Команды «Как исправить» остаются ручными."
                )
            )
        self.query_one("#diagnostics-confirmation", Static).update(confirmation)
        self.query_one("#diagnostics-confirmation").display = bool(confirmation)
        self.query_one("#diagnostics-report", Static).update(text)
        self.query_one("#diagnostics-report").display = bool(text)
        if self._report is None:
            self.query_one("#diagnostics-pair").display = False
        else:
            self.query_one("#diagnostics-pair").display = True

    def _strip_text(self) -> str:
        """`Project: <name> · mode: <mode> · report built <time>`; the time is the screen's own,
        taken when the report arrived (`Report` carries none)."""
        language = getattr(self.app, "language", "ru")
        online = self._report.online if self._report else self._requested_online
        mode = i18n.tr(language, "онлайн" if online else "офлайн")
        if self._built_at is not None:
            template = "Проект: {name} · режим: {mode} · отчёт построен {when}"
        elif self._state == "failed":
            template = "Проект: {name} · режим: {mode} · отчёт не построен"
        else:
            template = "Проект: {name} · режим: {mode} · отчёт строится"
        when = self._built_at.strftime("%H:%M") if self._built_at else ""
        return i18n.tr(language, template).format(
            name=self.repo.name, mode=mode, when=when
        )

    def _cli_line(self) -> str:
        """One muted line: the health command with the flags of the three actions."""
        language = self._language

        def tr(text: str) -> str:
            return i18n.tr(language, text)

        def short(*flags: str) -> str:
            return short_repo(console_data.health_cli_line(self.repo, *flags), self.repo)

        fix = ("--online", "--fix") if self._report and self._report.online else ("--fix",)
        return (
            f"$ {short()} · --online {tr('для «Онлайн»')} · "
            f"{' '.join(fix)} {tr('для «Исправить» (два шага)')} · "
            f"{tr('○ не проверено ≠ успешно')}"
        )

    def _render_overview(self) -> None:
        report = self._report
        summary = Text()

        def tr(text: str) -> str:
            return i18n.tr(self._language, text)

        narrow = self.app.size.width < brand.NARROW_WIDTH
        total = 0
        group_count = 0
        if report is not None:
            counts = report.summary()
            for status, label in (
                ("ok", "успешно"),
                ("warn", "предупреждения"),
                ("fail", "ошибки"),
                ("skipped", "не проверено"),
            ):
                summary.append_text(_icon(status, muted=counts[status] == 0))
                short = {
                    "ok": "ок",
                    "warn": "предупр.",
                    "fail": "ошибки",
                    "skipped": "не пров.",
                }
                summary.append(
                    f"{counts[status]} {tr(short[status] if narrow else label)}  "
                )
            total = len(report.checks)
            group_count = len({check.group for check in report.checks})
            if not narrow:
                summary.append(
                    "· "
                    + tr("проверено {checked} из {total}").format(
                        checked=total - counts["skipped"], total=total
                    )
                )
        self.query_one("#diagnostics-summary", Static).update(summary)
        self.query_one("#diagnostics-summary").display = report is not None
        self.query_one("#diagnostics-cli", Static).update(self._cli_line())
        self.query_one("#checks-list-card", SectionCard).set_note(
            f"{total} · {tr('групп:')} {group_count}" if report is not None else ""
        )
        for status in ("all", "fail", "warn", "skipped"):
            label = (
                tr("Все")
                if status == "all"
                else f"{brand.STATUS_ICONS[status]} {report.summary()[status] if report else 0}"
            )
            button = self.query_one(f"#filter-{status}", Button)
            button.label = label
            button.variant = "primary" if self._filter == status else "default"
        self.query_one(WrappedValue).set_value(self._strip_text())

    def _replace_contents(self, selector: str, *widgets: Widget) -> None:
        async def replace() -> None:
            container = self.query_one(selector)
            await container.remove_children()
            if self.is_mounted and not self._disposed:
                await container.mount(*widgets)

        self.run_worker(replace(), group=f"render-{selector}", exclusive=True)

    def _check_row(self, check: CheckResult) -> Text:
        """A list row: the status symbol and id, then the muted message."""
        text = _icon(check.status)
        text.append(check.id, style=f"bold {brand.PALETTE['foreground']}")
        group = GROUP_LABELS_RU.get(check.group, check.group)
        text.append(f"  {i18n.tr(self._language, group)}", style=brand.PALETTE["muted"])
        text.append("\n" + check.message, style=brand.PALETTE["muted"])
        return text

    def _render_groups(self) -> None:
        """The checks of the filter, problems first, as the list of the master-detail pair."""
        self._render_overview()
        if self._report is None:
            return
        rank = {"fail": 0, "warn": 1, "skipped": 2, "ok": 3}
        checks = sorted(
            (
                check
                for check in self._report.checks
                if self._filter == "all" or check.status == self._filter
            ),
            key=lambda check: rank[check.status],
        )
        self._shown = checks
        listing = self.query_one("#check-list", ListView)
        listing.clear()
        if not checks:
            listing.append(
                ListItem(
                    Static(
                        i18n.tr(self._language, "Нет проверок для этого фильтра"),
                        id="diagnostics-empty",
                        classes="no-i18n",
                        markup=False,
                    ),
                    disabled=True,
                )
            )
            self._selected = None
            self._show_check(None)
            return
        listing.extend(
            ListItem(Static(self._check_row(check), classes="no-i18n"), name=str(index))
            for index, check in enumerate(checks)
        )
        listing.index = 0
        self._show_check(checks[0])

    def _show_check(self, check: CheckResult | None) -> None:
        """The details of the highlighted check: status, message, remedy, the command and the
        section that deals with it."""
        self._selected = check
        language = self._language
        detail = Text()
        remedy = Text()
        command = ""
        if check is not None:
            detail.append_text(_icon(check.status))
            detail.append(check.id + "\n", style=f"bold {brand.PALETTE['foreground']}")
            group = GROUP_LABELS_RU.get(check.group, check.group)
            detail.append(i18n.tr(language, group) + "\n", style=brand.PALETTE["muted"])
            detail.append(check.message)
            fix = check.fix
            remedy = Text(
                i18n.tr(language, "Как исправить:") + " " + fix.text
                if fix
                else i18n.tr(language, "Рекомендация отсутствует"),
                style=brand.PALETTE["muted"],
            )
            command = (
                fix.command
                if fix and fix.command
                else i18n.tr(language, "Команда отсутствует — проверьте настройки вручную")
            )
        self.query_one("#check-detail", Static).update(detail)
        self.query_one("#check-remedy", Static).update(remedy)
        self.query_one("#check-command", Static).update(command)
        self.query_one("#check-command").display = check is not None
        has_command = bool(check and check.fix and check.fix.command)
        self.query_one("#copy-check-command", Button).display = has_command
        jump = self.query_one("#check-jump", JumpLink)
        jump.display = check is not None
        if check is not None:
            jump.section = check_route(check.id).section
            jump.relabel()

    @on(ListView.Highlighted, "#check-list")
    def _check_highlighted(self, event: ListView.Highlighted) -> None:
        event.stop()
        name = event.item.name if event.item is not None else None
        if name is not None and name.isdigit() and int(name) < len(self._shown):
            self._show_check(self._shown[int(name)])

    def _relabel_groups(self) -> None:
        if self._report is not None:
            self._render_groups()

    def on_resize(self, event: events.Resize) -> None:
        ConsoleShell.on_resize(self, event)
        if self.query("#diagnostics-summary"):
            self._render_overview()

    def _apply_button(self) -> Button:
        """Возвращает кнопку применения фиксов экрана."""
        return self.query_one("#apply-fixes", Button)
