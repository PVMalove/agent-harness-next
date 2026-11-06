"""The task board of the Web console in the terminal: one spec, its tickets as one list grouped by
status (five side-by-side columns do not fit a character grid), a segment filter by status, the
highlighted card beside the list and a card modal. The server owns the tracker read and the order of
the cards; this screen only renders the snapshot and never changes a ticket. Drag & drop from the
browser has no terminal equivalent; the card modal is the keyboard route to the ready agent prompt."""

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
)

from ...kernel import brand, i18n
from ...kernel.task_board import BoardCard, BoardSnapshot, BoardSpecs
from ..client import ConsoleClientError, ScreenClient
from ..shell import SHELL_CSS, ConsoleShell, ElidedPath, SectionCard, ShellIds
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


# Narrow terminals get the short status names, so the segment fits 80 columns.
_SHORT = {"ready": "К работе", "review": "Review"}


def _column_label(column: str, language: str) -> str:
    return i18n.tr(language, next(label for key, label in COLUMNS if key == column))


def _short(text: str, limit: int) -> str:
    return brand.shorten(" ".join(text.split()), limit)


def _card_text(card: BoardCard, language: str) -> Text:
    """A list row: the number, priority and title, then the muted blockers, command, batch and PR."""
    primary, muted, warning = (
        brand.PALETTE["primary"],
        brand.PALETTE["muted"],
        brand.PALETTE["warning"],
    )
    text = Text(no_wrap=True, overflow="ellipsis")
    if card.n is not None:
        text.append(f"#{card.n}  ", style=f"bold {primary}")
    if card.priority is not None:
        text.append(card.priority.removeprefix("priority::") + "  ", style=warning)
    text.append(card.title + "\n", style=f"bold {brand.PALETTE['foreground']}")
    meta: list[str] = []
    if card.open_blockers:
        meta.append(
            f"{brand.STATUS_ICONS['warn']} {i18n.tr(language, 'Блокеры').lower()} {card.open_blockers}"
        )
    else:
        meta.append(f"{brand.STATUS_ICONS['ok']} {i18n.tr(language, 'без блокеров')}")
    if card.command:
        meta.append(card.command)
    if card.batch:
        meta.append(card.batch)
    if card.pr is not None:
        meta.append(card.pr.ref)
    text.append(" · ".join(meta), style=muted)
    return text


def _detail_text(card: BoardCard, language: str) -> Text:
    """The card panel: facts, context, blockers and criteria; the prompt stays in the modal."""
    muted, primary = brand.PALETTE["muted"], brand.PALETTE["primary"]
    text = Text()
    text.append(card.title + "\n", style=f"bold {brand.PALETTE['foreground']}")
    facts = [
        _column_label(card.column, language),
        f"SP {card.sp}" if card.sp is not None else "",
        card.branch or "",
        card.dispatch or "",
    ]
    text.append(" · ".join(part for part in facts if part) + "\n", style=muted)
    if card.what:
        text.append("\n" + i18n.tr(language, "Контекст") + "\n", style=f"bold {primary}")
        text.append(_short(card.what, 400) + "\n")
    if card.blockers:
        text.append("\n" + i18n.tr(language, "Блокеры") + "\n", style=f"bold {primary}")
        icons = {
            "open": brand.STATUS_ICONS["fail"],
            "closed": brand.STATUS_ICONS["ok"],
            "unknown": brand.STATUS_ICONS["warn"],
        }
        for blocker in card.blockers:
            text.append(f"{icons[blocker.state]} {blocker.id} {blocker.why}".rstrip() + "\n")
    if card.criteria:
        text.append("\n" + i18n.tr(language, "Критерии") + "\n", style=f"bold {primary}")
        for item in card.criteria[:8]:
            text.append(f"• {_short(item, 120)}\n")
    text.append("\n" + i18n.tr(language, "Enter — промпт и полная карточка"), style=muted)
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

    SECTION = "Board"
    IS_SECTION_ROOT = True
    CRUMBS = "Главная › Доска задач"
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
    BoardScreen #board-controls { margin-bottom: 1; }
    BoardScreen #board-control-row { height: 1; margin-bottom: 1; }
    BoardScreen #board-spec { width: 1fr; margin-right: 1; }
    BoardScreen #board-refresh { width: auto; }
    BoardScreen #board-filter-fields { height: 1; }
    BoardScreen #board-search, BoardScreen #board-spec, BoardScreen #board-priority { height: 1; }
    BoardScreen #board-search { width: 1fr; margin-right: 1; }
    BoardScreen #board-priority { width: 24; margin-right: 1; }
    BoardScreen #board-free { width: auto; }
    BoardScreen #board-status-line { height: 1; margin-bottom: 1; }
    BoardScreen #board-live { width: 2; height: 1; color: $primary; }
    BoardScreen #board-status { width: 1fr; height: 1; color: $text-muted; }
    BoardScreen #board-segment { height: 1; margin-bottom: 1; overflow: hidden hidden; }
    BoardScreen #board-segment Button { height: 1; min-width: 0; border: none; padding: 0 1; color: $text-muted; }
    BoardScreen #board-segment Button.-on { background: $selection-background; color: $selection-foreground; text-style: bold; }
    BoardScreen #board-body { height: 1fr; }
    BoardScreen #board-list-card { width: 1fr; height: 1fr; }
    BoardScreen #board-detail-card { width: 44; height: 1fr; margin-left: 1; }
    BoardScreen #board-list { height: 1fr; border: none; padding: 0; background: transparent; }
    BoardScreen #board-list > ListItem { height: auto; padding: 0 1; border-left: solid transparent; }
    BoardScreen #board-list > ListItem.board-group { height: 1; margin-top: 1; padding: 0 1; color: $text-muted; text-style: bold; }
    BoardScreen #board-list > ListItem.board-group:first-of-type { margin-top: 0; }
    BoardScreen #board-list > ListItem.-highlight, BoardScreen #board-list:focus > ListItem.-highlight { background: $row-highlight; color: $foreground; border-left: solid $selection-edge; }
    BoardScreen #board-body.-empty, BoardScreen #board-body.-empty #board-list-card, BoardScreen #board-body.-empty #board-list { height: auto; }
    BoardScreen #board-body.-empty #board-detail-card { display: none; }
    BoardScreen #board-detail-scroll { height: 1fr; }
    BoardScreen #board-detail { height: auto; }
    BoardScreen .board-empty { color: $text-muted; height: auto; padding: 1; }
    BoardScreen .board-error { color: $error; height: auto; }
    BoardScreen.-narrow #board-priority { width: 18; }
    BoardScreen.-narrow #board-detail-card { display: none; }
    BoardScreen.-narrow #board-controls { margin-bottom: 0; }
    BoardScreen.-narrow #board-status-line, BoardScreen.-narrow #board-segment { margin-bottom: 0; }
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
        self._column = "all"
        self._shown: list[BoardCard] = []

    def compose_strip(self) -> ComposeResult:
        yield ElidedPath(str(self.repo))
        yield Static(
            "Трекер читается сервером; карточки не меняются из TUI", classes="no-i18n"
        )

    def compose_content(self) -> ComposeResult:
        language = self._language()
        with Vertical(id="board-page"):
            with SectionCard(title="Спека", id="board-controls"):
                with Horizontal(id="board-control-row"):
                    yield Select(
                        (),
                        prompt=i18n.tr(language, "Спека"),
                        id="board-spec",
                        allow_blank=True,
                        compact=True,
                    )
                    yield Button(
                        i18n.tr(language, "Обновить"), id="board-refresh", compact=True
                    )
                with Horizontal(id="board-filter-fields"):
                    yield Input(
                        placeholder=i18n.tr(language, "Поиск по тикетам"),
                        id="board-search",
                        compact=True,
                    )
                    yield Select(
                        (
                            (i18n.tr(language, label), value)
                            for label, value in _PRIORITIES
                        ),
                        prompt=i18n.tr(language, "Все приоритеты"),
                        id="board-priority",
                        compact=True,
                    )
                    yield Checkbox(
                        i18n.tr(language, "Без блокеров"), id="board-free"
                    )
            with Horizontal(id="board-status-line"):
                yield LiveDot(id="board-live")
                yield Static("", id="board-status")
            with Horizontal(id="board-segment"):
                yield from self._segment_buttons()
            with Horizontal(id="board-body"):
                with SectionCard(title="Задачи", id="board-list-card"):
                    yield ListView(id="board-list")
                with SectionCard(title="Карточка", id="board-detail-card"):
                    with VerticalScroll(id="board-detail-scroll"):
                        yield Static("", id="board-detail", classes="no-i18n", markup=False)

    def _segment_labels(self) -> dict[str, str]:
        """Each segment button's text: the status, then the number of shown cards."""
        language = self._language()
        counts = self._counts()
        narrow = self.size.width < brand.NARROW_WIDTH
        labels = {"all": f"{i18n.tr(language, 'Все')} {sum(counts.values())}"}
        for key, label in COLUMNS:
            name = _SHORT.get(key, label) if narrow else label
            labels[key] = f"{i18n.tr(language, name)} {counts[key]}"
        return labels

    def _segment_buttons(self) -> ComposeResult:
        """One compact button per status and one for all of them, each with its card count."""
        for key, label in self._segment_labels().items():
            yield Button(
                label,
                id=f"board-seg-{key}",
                compact=True,
                classes="-on" if self._column == key else "",
            )

    def _counts(self) -> dict[str, int]:
        """The shown cards per status; before the first board they are all zero."""
        counts = {key: 0 for key, _label in COLUMNS}
        if self._board is not None:
            for card in self._board.tickets:
                if self._visible(card) and card.column in counts:
                    counts[card.column] += 1
        return counts

    def on_mount(self) -> None:
        super().on_mount()
        self._load_specs()

    def on_resize(self, event: events.Resize) -> None:
        super().on_resize(event)
        if self.query("#board-seg-all"):
            self._paint_segment()
        self.query_one("#board-body").set_class(not self._shown, "-empty")

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
        language = self._language()
        cards = (
            [card for card in board.tickets if self._visible(card)]
            if board is not None
            else []
        )
        self._shown = [
            card for card in cards if self._column in ("all", card.column)
        ]
        self._fill_list(self.query_one("#board-list", ListView), language)
        self._paint_segment()
        self.query_one("#board-list-card", SectionCard).set_note(str(len(self._shown)))
        self._show_detail(self._shown[0] if self._shown else None)

    def _fill_list(self, list_view: ListView, language: str) -> None:
        """The shown cards in board order, a muted heading before each status when all are shown."""
        list_view.clear()
        if not self._shown:
            list_view.extend(
                [
                    ListItem(
                        Static(
                            i18n.tr(language, "Карточек нет"),
                            classes="board-empty",
                            markup=False,
                        ),
                        disabled=True,
                    )
                ]
            )
            return
        items: list[ListItem] = []
        previous = ""
        for card in self._shown:
            if self._column == "all" and card.column != previous:
                previous = card.column
                total = sum(1 for item in self._shown if item.column == card.column)
                items.append(
                    ListItem(
                        Static(
                            f"{_column_label(card.column, language).upper()}  {total}",
                            classes="no-i18n",
                            markup=False,
                        ),
                        classes="board-group",
                        disabled=True,
                    )
                )
            items.append(
                ListItem(
                    Static(_card_text(card, language), classes="no-i18n", markup=False),
                    name=card.id,
                )
            )
        list_view.extend(items)
        first = next((i for i, item in enumerate(items) if item.name), 0)
        list_view.index = first

    def _paint_segment(self) -> None:
        """The counts and the selected status on the segment buttons, in place."""
        for key, label in self._segment_labels().items():
            button = self.query_one(f"#board-seg-{key}", Button)
            button.label = label
            button.set_class(self._column == key, "-on")

    def _show_detail(self, card: BoardCard | None) -> None:
        """The highlighted card beside the list: facts, blockers and criteria."""
        if not self.query("#board-detail"):
            return
        self.query_one("#board-detail", Static).update(
            _detail_text(card, self._language()) if card else Text("")
        )

    @on(ListView.Highlighted, "#board-list")
    def _card_highlighted(self, event: ListView.Highlighted) -> None:
        event.stop()
        name = event.item.name if event.item is not None else None
        card = next((item for item in self._shown if item.id == name), None)
        if card is not None:
            self._show_detail(card)

    @on(Button.Pressed, "#board-segment Button")
    def _segment_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self._column = str(event.button.id).removeprefix("board-seg-")
        self._render_board()

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
