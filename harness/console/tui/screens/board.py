"""The task board of the Web console in the terminal: one spec, its five columns, filters and a
card modal. The server owns the tracker read; this screen only renders the snapshot and never
changes a ticket. Drag & drop from the browser has no terminal equivalent; the card modal is the
keyboard route to the same facts and the ready agent prompt."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    ListItem,
    ListView,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from ...kernel import brand, i18n
from ...kernel.task_board import BoardCard, BoardSnapshot, BoardSpecs
from ..client import ConsoleClientError, ScreenClient
from ..shell import SHELL_CSS, ConsoleShell, ElidedPath, Fold, ShellIds
from ..widgets import LiveDot
from ..translate import Translated
from .commands import call_from_worker

COLUMNS = (
    ("backlog", "Бэклог"),
    ("ready", "Готово к работе"),
    ("progress", "В работе"),
    ("review", "Review / QA"),
    ("done", "Готово"),
)
_PRIORITIES = (
    ("Все приоритеты", "all"),
    ("p0", "priority::p0"),
    ("p1", "priority::p1"),
    ("p2", "priority::p2"),
    ("p3", "priority::p3"),
)


def _column_label(column: str, language: str) -> str:
    return i18n.tr(language, next(label for key, label in COLUMNS if key == column))


def _short(text: str, limit: int) -> str:
    return brand.shorten(" ".join(text.split()), limit)


def _card_text(card: BoardCard, language: str) -> Text:
    primary, muted, warning = (
        brand.PALETTE["primary"],
        brand.PALETTE["muted"],
        brand.PALETTE["warning"],
    )
    text = Text()
    if card.n is not None:
        text.append(f"#{card.n}  ", style=f"bold {primary}")
    if card.priority is not None:
        text.append(card.priority.removeprefix("priority::") + "  ", style=warning)
    text.append(card.title + "\n", style=f"bold {brand.PALETTE['foreground']}")
    if card.what:
        text.append(_short(card.what, 96) + "\n", style=muted)
    meta: list[str] = []
    if card.open_blockers:
        meta.append(f"{brand.STATUS_ICONS['warn']} {card.open_blockers}")
    else:
        meta.append(brand.STATUS_ICONS["ok"])
    if card.command:
        meta.append(card.command)
    if card.batch:
        meta.append(card.batch)
    if card.pr is not None:
        meta.append(card.pr.ref)
    text.append(" · ".join(meta), style=muted)
    return text


class BoardCardModal(Translated, ModalScreen[None]):
    """A card's context, acceptance criteria and ready prompt; copying never changes the ticket."""

    BINDINGS = [Binding("escape", "dismiss", "Закрыть")]

    DEFAULT_CSS = brand.shell_css("""
    BoardCardModal { align: center middle; }
    BoardCardModal > Vertical {
        width: 90%; max-width: 120; height: 85%; padding: 0 1;
        border: round $component-border; background: $surface;
    }
    BoardCardModal #board-card-scroll { height: 1fr; }
    BoardCardModal .board-card-title { height: auto; text-style: bold; color: $foreground; }
    BoardCardModal .board-card-meta { height: auto; color: $text-muted; }
    BoardCardModal .board-card-section { height: auto; margin-top: 1; text-style: bold; color: $primary; }
    BoardCardModal .board-card-body { height: auto; color: $foreground; }
    BoardCardModal .actions { height: auto; margin-top: 1; }
    BoardCardModal Button { margin-right: 1; border: round $component-border; }
    BoardCardModal Button:hover, BoardCardModal Button:focus { border: round $primary; color: $primary; }
    """)

    def __init__(self, card: BoardCard, language: str = "ru") -> None:
        super().__init__()
        self.card = card
        self._language = language

    def compose(self) -> ComposeResult:
        card = self.card
        language = self._language
        with Vertical(id="board-card-dialog") as dialog:
            dialog.border_title = brand.frame_title(
                f"#{card.n}" if card.n is not None else card.id
            )
            with VerticalScroll(id="board-card-scroll"):
                yield Static(card.title, classes="board-card-title", markup=False)
                meta = [
                    _column_label(card.column, language),
                    card.command,
                    f"SP {card.sp}" if card.sp is not None else "",
                    card.branch or "",
                    card.pr.ref if card.pr is not None else "",
                    card.batch or "",
                ]
                yield Static(
                    " · ".join(part for part in meta if part),
                    classes="board-card-meta",
                    markup=False,
                )
                if card.labels:
                    yield Static(
                        " · ".join(card.labels), classes="board-card-meta", markup=False
                    )
                yield Static(
                    i18n.tr(language, "Контекст"), classes="board-card-section"
                )
                yield Static(card.what or "—", classes="board-card-body", markup=False)
                if card.blockers:
                    yield Static(
                        i18n.tr(language, "Блокеры"), classes="board-card-section"
                    )
                    for blocker in card.blockers:
                        state = {
                            "open": brand.STATUS_ICONS["fail"],
                            "closed": brand.STATUS_ICONS["ok"],
                            "unknown": brand.STATUS_ICONS["warn"],
                        }[blocker.state]
                        yield Static(
                            f"{state} {blocker.id} · {blocker.why}".rstrip(" ·"),
                            classes="board-card-body",
                            markup=False,
                        )
                if card.criteria:
                    yield Static(
                        i18n.tr(language, "Критерии"), classes="board-card-section"
                    )
                    for item in card.criteria:
                        yield Static(
                            f"• {item}", classes="board-card-body", markup=False
                        )
                if card.files:
                    yield Static("Relevant Files", classes="board-card-section")
                    for path, why in card.files:
                        yield Static(
                            f"{path} — {why}".rstrip(" —"),
                            classes="board-card-body",
                            markup=False,
                        )
                yield Static(i18n.tr(language, "Промпт"), classes="board-card-section")
                yield Static(card.prompt, classes="board-card-body", markup=False)
            with Horizontal(classes="actions"):
                yield Button(
                    i18n.tr(language, "Промпт"), id="copy-prompt", compact=True
                )
                yield Button(
                    i18n.tr(language, "Критерии"), id="copy-criteria", compact=True
                )
                yield Button(
                    i18n.tr(language, "Закрыть"), id="close-card", compact=True
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "copy-prompt":
            self.app.copy_to_clipboard(self.card.prompt)
            self.app.notify("Промпт скопирован")
        elif event.button.id == "copy-criteria":
            self.app.copy_to_clipboard("\n".join(self.card.criteria))
            self.app.notify("Критерии скопированы")
        else:
            self.dismiss(None)


class BoardScreen(ConsoleShell):
    """The task board of one spec, opened from Orchestration: specs, five columns, filters and
    the card modal. It reads the tracker only; the status and tickets stay the tracker's."""

    SECTION = "Orchestration"
    IS_SECTION_ROOT = False
    CRUMBS = "Главная › Оркестрация › Доска задач"
    HAS_CONTEXT = False
    NARROW_FOOTER_KEYS = ("escape", "r", "f2")
    AUTO_FOCUS = "#board-spec"
    IDS = ShellIds(
        navigation="board-navigation",
        menu="board-sections",
        content="board-main",
        breadcrumbs="board-breadcrumbs",
        toggle="board-menu",
        body="board-body",
        context="board-context",
    )
    BINDINGS = [Binding("r", "refresh", "Обновить")]
    CSS = SHELL_CSS + brand.shell_css("""
    BoardScreen #board-page { height: 1fr; padding: 0 2; }
    BoardScreen #board-controls { height: auto; margin-bottom: 1; }
    BoardScreen #board-control-row { height: auto; }
    BoardScreen #board-spec { width: 1fr; margin-right: 1; }
    BoardScreen #board-refresh { width: auto; }
    BoardScreen #board-filters { height: auto; margin-top: 1; }
    BoardScreen #board-filter-fields { height: auto; }
    BoardScreen #board-search { width: 1fr; margin-bottom: 1; }
    BoardScreen #board-status-line { height: 1; margin-bottom: 1; }
    BoardScreen #board-live { width: 2; height: 1; color: $primary; }
    BoardScreen #board-status { width: 1fr; height: 1; color: $text-muted; }
    BoardScreen #board-columns-wide { height: 1fr; }
    BoardScreen .board-column { width: 1fr; height: 1fr; margin-right: 1; }
    BoardScreen .board-column:last-of-type { margin-right: 0; }
    BoardScreen .board-column-title { height: 1; color: $text-muted; text-style: bold; }
    BoardScreen #board-tabs { display: none; height: 1fr; }
    BoardScreen TabPane { height: 1fr; }
    BoardScreen.-narrow #board-columns-wide { display: none; }
    BoardScreen.-narrow #board-tabs { display: block; }
    BoardScreen .board-list { height: 1fr; border: round $border-subtle; background: $surface; }
    BoardScreen .board-list > ListItem { height: auto; padding: 1; border-left: solid transparent; border-bottom: solid $border-subtle; }
    BoardScreen .board-list > ListItem.-highlight, BoardScreen .board-list:focus > ListItem.-highlight { background: $row-highlight; color: $foreground; border-left: solid $selection-edge; }
    BoardScreen .board-empty { color: $text-muted; height: auto; padding: 1; }
    BoardScreen .board-error { color: $error; height: auto; }
    BoardScreen.-narrow #board-controls { height: auto; }
    BoardScreen.-narrow #board-spec, BoardScreen.-narrow #board-search { width: 100%; margin-right: 0; }
    """)

    def __init__(self, repo: Path, client: ScreenClient) -> None:
        super().__init__()
        self.repo = repo
        self._client = client
        self._specs: BoardSpecs | None = None
        self._board: BoardSnapshot | None = None
        self._error = ""
        self._busy = False
        self._epoch = 0
        self._query = ""
        self._priority = "all"
        self._only_free = False

    def compose_strip(self) -> ComposeResult:
        yield ElidedPath(str(self.repo))
        yield Static(
            "Трекер читается сервером; карточки не меняются из TUI", classes="no-i18n"
        )

    def compose_content(self) -> ComposeResult:
        with Vertical(id="board-page"):
            with Vertical(id="board-controls"):
                with Horizontal(id="board-control-row"):
                    yield Select(
                        (),
                        prompt=i18n.tr(self._language(), "Спека"),
                        id="board-spec",
                        allow_blank=True,
                    )
                    yield Button(
                        i18n.tr(self._language(), "Обновить"),
                        id="board-refresh",
                        compact=True,
                    )
                with Fold(
                    title="Фильтры",
                    summary="поиск · приоритет · блокеры",
                    collapsed=True,
                    id="board-filters",
                ):
                    with Vertical(id="board-filter-fields"):
                        yield Input(
                            placeholder=i18n.tr(self._language(), "Поиск по тикетам"),
                            id="board-search",
                        )
                        yield Select(
                            (
                                (i18n.tr(self._language(), label), value)
                                for label, value in _PRIORITIES
                            ),
                            prompt=i18n.tr(self._language(), "Все приоритеты"),
                            id="board-priority",
                        )
                        yield Checkbox(
                            i18n.tr(self._language(), "Только без блокеров"),
                            id="board-free",
                        )
            with Horizontal(id="board-status-line"):
                yield LiveDot(id="board-live")
                yield Static("", id="board-status")
            with Horizontal(id="board-columns-wide"):
                for key, label in COLUMNS:
                    with Vertical(classes="board-column"):
                        yield Static(
                            i18n.tr(self._language(), label),
                            classes="board-column-title",
                        )
                        yield ListView(id=f"board-col-{key}", classes="board-list")
            with TabbedContent(id="board-tabs"):
                for key, label in COLUMNS:
                    with TabPane(
                        i18n.tr(self._language(), label), id=f"board-tab-{key}"
                    ):
                        yield ListView(id=f"board-list-{key}", classes="board-list")

    def on_mount(self) -> None:
        super().on_mount()
        self._fit_filters()
        self._load_specs()

    def on_resize(self, event: events.Resize) -> None:
        super().on_resize(event)
        self._fit_filters()

    def _fit_filters(self) -> None:
        if self.query("#board-filters"):
            self.query_one("#board-filters", Fold).collapsed = (
                self.size.width < brand.NARROW_WIDTH
            )

    def _language(self) -> str:
        return getattr(self.app, "language", "ru")

    def _set_status(self, text: str, *, error: bool = False) -> None:
        status = self.query_one("#board-status", Static)
        status.update(text)
        status.set_class(error, "board-error")
        if self.query("#board-live"):
            self.query_one("#board-live", LiveDot).display = self._busy

    def _load_specs(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._epoch += 1
        epoch = self._epoch
        self._set_status("Читаю спеки…")
        client = self._client

        def work() -> None:
            try:
                specs = client.task_board_specs()
            except ConsoleClientError as exc:
                message = str(exc)
                call_from_worker(self, lambda: self._failed(message, epoch))
                return
            call_from_worker(self, lambda: self._specs_loaded(specs, epoch))

        self.run_worker(work, thread=True, exclusive=True, group="board-specs")

    def _specs_loaded(self, specs: BoardSpecs, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._busy = False
        self._specs = specs
        selector = self.query_one("#board-spec", Select)
        selector.set_options((spec.title, spec.id) for spec in specs.specs)
        if not specs.specs:
            self._set_status("Открытых спек нет", error=False)
            self._render_board()
            return
        first = specs.specs[0]
        if selector.value == first.id:
            self._load_board(first.id)
        else:
            selector.value = first.id
        self._set_status("Спек: " + str(len(specs.specs)))

    def _load_board(self, spec_id: str) -> None:
        self._epoch += 1
        epoch = self._epoch
        self._busy = True
        self._set_status("Читаю доску…")
        client = self._client

        def work() -> None:
            try:
                board = client.task_board(spec_id)
            except ConsoleClientError as exc:
                message = str(exc)
                call_from_worker(self, lambda: self._failed(message, epoch))
                return
            call_from_worker(self, lambda: self._board_loaded(board, epoch))

        self.run_worker(work, thread=True, exclusive=True, group="board")

    def _board_loaded(self, board: BoardSnapshot, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._busy = False
        self._board = board
        self._error = ""
        self._set_status(
            f"Трекер: {board.tracker} · открыто {board.kpis.get('open', 0)} из {board.kpis.get('total', 0)}"
        )
        self._render_board()

    def _failed(self, message: str, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._busy = False
        self._error = message
        self._set_status(message, error=True)
        self._render_board()

    def _visible(self, card: BoardCard) -> bool:
        if self._query:
            haystack = " ".join((card.title, card.what, *card.labels)).casefold()
            if self._query not in haystack:
                return False
        if self._priority != "all" and card.priority != self._priority:
            return False
        if self._only_free and card.open_blockers:
            return False
        return True

    def _render_board(self) -> None:
        if not self.is_mounted:
            return
        board = self._board
        for key, _label in COLUMNS:
            cards = []
            if board is not None:
                cards = [
                    card
                    for card in board.tickets
                    if card.column == key and self._visible(card)
                ]
            for prefix in ("board-list", "board-col"):
                if self.query(f"#{prefix}-{key}"):
                    self._fill_cards(
                        self.query_one(f"#{prefix}-{key}", ListView), cards
                    )

    def _fill_cards(self, list_view: ListView, cards: list[BoardCard]) -> None:
        list_view.clear()
        if not cards:
            list_view.extend(
                [
                    ListItem(
                        Static(
                            i18n.tr(self._language(), "Карточек нет"),
                            classes="board-empty",
                            markup=False,
                        ),
                        disabled=True,
                    )
                ]
            )
            return
        list_view.extend(
            ListItem(
                Static(
                    _card_text(card, self._language()),
                    classes="no-i18n",
                    markup=False,
                ),
                name=card.id,
            )
            for card in cards
        )

    @on(Select.Changed, "#board-spec")
    def _spec_changed(self, event: Select.Changed) -> None:
        if self._busy:
            return
        if event.value is not Select.BLANK and isinstance(event.value, str):
            self._load_board(event.value)

    @on(Input.Changed, "#board-search")
    def _search_changed(self, event: Input.Changed) -> None:
        self._query = event.value.strip().casefold()
        self._render_board()

    @on(Select.Changed, "#board-priority")
    def _priority_changed(self, event: Select.Changed) -> None:
        self._priority = event.value if isinstance(event.value, str) else "all"
        self._render_board()

    @on(Checkbox.Changed, "#board-free")
    def _free_changed(self, event: Checkbox.Changed) -> None:
        self._only_free = event.value
        self._render_board()

    @on(Button.Pressed, "#board-refresh")
    def _refresh(self, event: Button.Pressed) -> None:
        event.stop()
        if self._board is not None:
            self._load_board(self._board.spec.id)

    def action_refresh(self) -> None:
        if self._board is not None:
            self._load_board(self._board.spec.id)
        else:
            self._load_specs()

    @on(ListView.Selected)
    def _card_selected(self, event: ListView.Selected) -> None:
        if not event.item.name or self._board is None:
            return
        card = next(
            (item for item in self._board.tickets if item.id == event.item.name), None
        )
        if card is None:
            return
        event.stop()
        self.app.push_screen(BoardCardModal(card, self._language()))

    def sync_language(self) -> None:
        if self.query("#board-priority"):
            self.query_one("#board-priority", Select).set_options(
                (
                    (i18n.tr(self._language(), label), value)
                    for label, value in _PRIORITIES
                )
            )
        if self._board is not None:
            self._render_board()
