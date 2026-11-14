"""Help screen: the console guide of the console server's `help.snapshot`, rendered as Markdown."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import ListItem, ListView, Markdown, Static

from ...kernel import brand, i18n
from ..client import ConsoleClientError, ScreenClient
from ..shell import SHELL_CSS, ConsoleShell, Fold, SectionCard
from .commands import call_from_worker

READING = "Читаю справку…"


def guide_parts(
    client: ScreenClient | None, language: str
) -> tuple[str, list[tuple[str, str]]]:
    """The introduction and the sections of the guide in `language`, read from the console
    server's `help.snapshot`; without the server, or when it does not answer, the introduction
    is the reason and there are no sections. Blocks: the screen calls it in a worker."""
    if client is None:
        return i18n.tr(language, "Справка недоступна: сервер консоли не подключён"), []
    try:
        guide = client.help(language)
    except ConsoleClientError as exc:
        return f"{i18n.tr(language, 'Справка недоступна:')} {exc}", []
    return guide.intro, list(guide.sections)


class HelpScreen(ConsoleShell):
    SECTION = "Help"
    CRUMBS = "Главная › Справка"
    AUTO_FOCUS = "#help-scroll"
    CSS = SHELL_CSS + brand.shell_css("""
    HelpScreen #help-layout { height: 1fr; }
    HelpScreen #help-toc-card { width: 27; height: auto; margin: 0 1 0 2; }
    HelpScreen #help-toc { width: 100%; height: auto; border: none; margin: 0; padding: 0; background: transparent; }
    HelpScreen #help-toc > ListItem { height: 1; }
    HelpScreen #help-scroll { width: 1fr; height: 1fr; padding: 0 2; }
    HelpScreen Markdown { padding: 0; }
    HelpScreen MarkdownH1 { margin: 0 0 1 0; padding: 0; border: none; content-align: left middle; }
    HelpScreen.shell .help-section { border: none; margin: 0; padding: 0; background: transparent; }
    HelpScreen.shell .help-section > Contents { padding: 0; }
    HelpScreen.shell .help-section > CollapsibleTitle { display: none; }
    HelpScreen.-narrow #help-toc-card { display: none; }
    HelpScreen.shell.-narrow .help-section { border: round $border-subtle; background: transparent; padding: 0 1; }
    HelpScreen.shell.-narrow .help-section > Contents { padding: 1 0 0 0; }
    HelpScreen.shell.-narrow .help-section > CollapsibleTitle { display: block; }
    HelpScreen.-narrow .help-section MarkdownH2 { display: none; }
    """)

    def __init__(self, client: ScreenClient | None) -> None:
        super().__init__()
        self._client = client
        self._help_narrow: bool | None = None
        self._navigation_blocked = False
        # A language switch outdates a read that is still running: its result is dropped.
        self._load_epoch = 0

    def compose_strip(self) -> ComposeResult:
        yield Static("", id="help-source", classes="no-i18n", markup=False)

    def compose_content(self) -> ComposeResult:
        language = getattr(self.app, "language", "ru")
        with Horizontal(id="help-layout"):
            with SectionCard(title="Содержание", id="help-toc-card"):
                yield ListView(id="help-toc")
            with VerticalScroll(id="help-scroll"):
                yield Markdown(i18n.tr(language, READING), id="help-text")

    def on_mount(self) -> None:
        self._update_source()
        self._load()

    def _load(self) -> None:
        """Read the guide in the console language from the server in a worker, then show it."""
        self._load_epoch += 1
        epoch, language = self._load_epoch, getattr(self.app, "language", "ru")

        def work() -> None:
            intro, parts = guide_parts(self._client, language)

            def done() -> None:
                if epoch == self._load_epoch:
                    self.call_later(self._show, intro, parts)

            call_from_worker(self, done)

        self.run_worker(work, thread=True, group="help", exclusive=True)

    async def _show(self, intro: str, parts: list[tuple[str, str]]) -> None:
        """Show the guide: the sections are updated in place when their number is unchanged (a
        language switch), otherwise mounted anew."""
        self.query_one("#help-text", Markdown).update(intro)
        toc = self.query_one("#help-toc", ListView)
        if len(self.query(".help-section")) == len(parts):
            for index, ((title, body), item) in enumerate(zip(parts, toc.children)):
                self.query_one(f"#help-body-{index}", Markdown).update(body)
                item.query_one(Static).update(title)
            return
        # Removed before mounting: the new sections reuse the ids of the old ones.
        await self.query(".help-section").remove()
        await toc.clear()
        await toc.extend(
            ListItem(Static(title, classes="no-i18n")) for title, _ in parts
        )
        narrow = self.size.width < brand.NARROW_WIDTH
        await self.query_one("#help-scroll", VerticalScroll).mount_all(
            Fold(
                Markdown(body, id=f"help-body-{index}"),
                title=title,
                id=f"help-section-{index}",
                classes="help-section",
                collapsed=narrow and index != 0,
            )
            for index, (title, body) in enumerate(parts)
        )
        self._help_narrow = None
        self.call_after_refresh(self._adapt_sections, self.size.width)

    def _update_source(self) -> None:
        language = getattr(self.app, "language", "ru")
        source = next(
            (
                screen.SECTION
                for screen in reversed(self.app.screen_stack[:-1])
                if isinstance(screen, ConsoleShell)
            ),
            None,
        )
        text = i18n.tr(language, "Справка F1")
        if source:
            label = i18n.section_label(language, source)
            text += f" · {i18n.tr(language, 'Вы пришли с экрана')}: {label}"
        if self._navigation_blocked:
            text += " · ⚠ " + i18n.tr(language, "Сначала завершите или отмените диалог")
        self.query_one("#help-source", Static).update(text)

    def _adapt_sections(self, width: int) -> None:
        narrow = width < brand.NARROW_WIDTH
        if self._help_narrow == narrow:
            return
        self._help_narrow = narrow
        for index, fold in enumerate(self.query(".help-section").results(Fold)):
            fold.collapsed = narrow and index != 0 and not fold.has_focus_within

    def on_resize(self, event: events.Resize) -> None:
        self._adapt_sections(event.size.width)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "help-toc":
            event.stop()
            index = event.list_view.index
            if index is not None:
                fold = self.query_one(f"#help-section-{index}", Fold)
                fold.collapsed = False
                fold.scroll_visible(top=True, animate=False)

    async def open_section(self, index: int) -> None:
        """Return through the opener's navigation guard instead of popping past a draft or dialog."""
        source = self.app.screen_stack[-2]
        if isinstance(source, ConsoleShell):
            self.dismiss(None)
            self.app.call_later(source.action_section, index)
        else:
            self._navigation_blocked = True
            self._update_source()

    def sync_language(self) -> None:
        super().sync_language()
        self._update_source()
        self._load()
