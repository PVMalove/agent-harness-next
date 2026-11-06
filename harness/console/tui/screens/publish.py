"""The Publish view from the console server's ledger: the candidate, PR/MR receipt and the
evidence that gates the human handoff. It is read-only: the TUI never creates a PR or merges one;
the browser's «Подготовить PR» is a human action, and the same rule holds here."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, ListItem, ListView, Static

from ...kernel import brand
from ...kernel.reports import BatchSummary, LedgerView, StageEntry
from ..client import ConsoleClientError, ScreenClient
from ..shell import SHELL_CSS, ConsoleShell, ElidedPath, SectionCard, ShellIds
from ..widgets import LiveDot
from .commands import call_from_worker


def _report_of(stages: list[StageEntry], role: str) -> StageEntry | None:
    return next(
        (stage for stage in stages if stage.role == role and stage.report is not None),
        None,
    )


def _candidate(stages: list[StageEntry]) -> str:
    review = _report_of(stages, "code-review") or _report_of(stages, "review")
    if review is None or review.report is None:
        return ""
    value = review.report.report.get("candidate_commit")
    return value if isinstance(value, str) else ""


class PublishScreen(ConsoleShell):
    """Candidate, PR/MR and evidence for the selected batch; all facts are read from the ledger."""

    SECTION = "Publish"
    IS_SECTION_ROOT = True
    CRUMBS = "Главная › Публикация"
    HAS_CONTEXT = False
    NARROW_FOOTER_KEYS = ("escape", "r", "f2")
    AUTO_FOCUS = "#publish-batches"
    IDS = ShellIds(
        navigation="publish-navigation",
        menu="publish-sections",
        content="publish-main",
        breadcrumbs="publish-breadcrumbs",
        toggle="publish-menu",
        body="publish-body",
        context="publish-context",
    )
    BINDINGS = [Binding("r", "refresh", "Обновить")]
    CSS = SHELL_CSS + brand.shell_css("""
    PublishScreen #publish-page { height: 1fr; padding: 0 2; }
    PublishScreen #publish-live { width: 2; height: 1; color: $primary; }
    PublishScreen #publish-body { height: 1fr; }
    PublishScreen #publish-list-panel { width: 36; height: 1fr; margin-right: 1; }
    PublishScreen #publish-batches { height: 1fr; border: none; background: transparent; }
    PublishScreen #publish-batches > ListItem { height: auto; padding: 0 1; border-left: solid transparent; }
    PublishScreen #publish-batches > ListItem.-highlight, PublishScreen #publish-batches:focus > ListItem.-highlight { background: $row-highlight; color: $foreground; border-left: solid $selection-edge; }
    PublishScreen #publish-detail { height: 1fr; }
    PublishScreen #publish-detail-title { height: auto; text-style: bold; color: $foreground; }
    PublishScreen #publish-detail-meta { height: auto; color: $text-muted; }
    PublishScreen #publish-detail-body { height: auto; }
    PublishScreen #publish-actions { height: auto; margin-top: 1; }
    PublishScreen #publish-actions Button { margin-right: 1; border: round $component-border; }
    PublishScreen #publish-actions Button:hover, PublishScreen #publish-actions Button:focus { border: round $primary; color: $primary; }
    PublishScreen.-narrow #publish-body { layout: vertical; }
    PublishScreen.-narrow #publish-list-panel { width: 100%; height: 10; margin-right: 0; }
    """)

    def __init__(self, repo: Path, client: ScreenClient) -> None:
        super().__init__()
        self.repo = repo
        self._client = client
        self._view: LedgerView | None = None
        self._selected: str | None = None
        self._error = ""
        self._busy = False
        self._epoch = 0

    def compose_strip(self) -> ComposeResult:
        yield ElidedPath(str(self.repo))
        yield LiveDot(id="publish-live")
        yield Static(
            "Публикация остаётся человеку: TUI не создаёт PR/MR и не выполняет merge",
            classes="no-i18n",
        )

    def compose_content(self) -> ComposeResult:
        with Vertical(id="publish-page"):
            with Horizontal(id="publish-body"):
                with SectionCard(title="Пакеты", id="publish-list-panel"):
                    yield ListView(id="publish-batches")
                with SectionCard(title="Preflight", id="publish-detail"):
                    with VerticalScroll():
                        yield Static("", id="publish-detail-title", markup=False)
                        yield Static("", id="publish-detail-meta", markup=False)
                        yield Static("", id="publish-detail-body", markup=False)
                        with Horizontal(id="publish-actions"):
                            yield Button(
                                "Копировать PR", id="publish-copy", compact=True
                            )
                            yield Button("Обновить", id="publish-refresh", compact=True)

    def on_mount(self) -> None:
        super().on_mount()
        self._load()

    def _load(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._epoch += 1
        epoch = self._epoch
        self._set_busy(True)
        self._set_title("Читаю леджер…")
        client = self._client

        def work() -> None:
            try:
                view = client.reports()
            except ConsoleClientError as exc:
                message = str(exc)
                call_from_worker(self, lambda: self._failed(message, epoch))
                return
            call_from_worker(self, lambda: self._loaded(view, epoch))

        self.run_worker(work, thread=True, exclusive=True, group="publish")

    def _set_busy(self, busy: bool) -> None:
        if self.query("#publish-live"):
            self.query_one("#publish-live", LiveDot).display = busy

    def _set_title(self, text: str) -> None:
        if self.query("#publish-detail-title"):
            self.query_one("#publish-detail-title", Static).update(text)

    def _failed(self, message: str, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._busy = False
        self._error = message
        self._set_busy(False)
        self._set_title(message)

    def _loaded(self, view: LedgerView, epoch: int) -> None:
        if epoch != self._epoch:
            return
        self._busy = False
        self._set_busy(False)
        self._view = view
        self._error = view.unavailable or ""
        batches = [batch for batch in view.batches if batch.batch_id]
        listing = self.query_one("#publish-batches", ListView)
        listing.clear()
        if not batches:
            listing.extend(
                [ListItem(Static("Пакетов нет", classes="board-empty"), disabled=True)]
            )
            self._set_title("Пакетов нет")
            return
        listing.extend(
            ListItem(
                Static(self._batch_row(batch), classes="no-i18n", markup=False),
                name=batch.batch_id,
            )
            for batch in batches
        )
        self._select(batches[0].batch_id)

    def _batch_row(self, batch: BatchSummary) -> Text:
        text = Text()
        text.append(batch.ticket or "—", style=f"bold {brand.PALETTE['primary']}")
        text.append(f"  {batch.state}\n", style=brand.PALETTE["muted"])
        pr = batch.pr_url or batch.pr_state
        if pr:
            text.append(pr, style=brand.PALETTE["muted"])
        return text

    def _select(self, batch_id: str) -> None:
        self._selected = batch_id
        view = self._view
        if view is None:
            return
        batch = next((item for item in view.batches if item.batch_id == batch_id), None)
        if batch is None:
            return
        stages = [stage for stage in view.stages if stage.batch_id == batch_id]
        review = _report_of(stages, "code-review") or _report_of(stages, "review")
        qa = _report_of(stages, "qa")
        publish = _report_of(stages, "publish")
        checks = (
            ("Review", review is not None),
            ("QA", qa is not None),
            ("PR", bool(batch.pr_url)),
            ("Publish", publish is not None),
        )
        self._set_title(f"{batch.ticket or '—'} · {batch.batch_id}")
        meta = [
            f"Состояние: {batch.state}",
            f"Ветка: {batch.branch or '—'}",
            f"PR: {batch.pr_url or '—'}",
            f"PR state: {batch.pr_state}",
            f"Кандидат: {_candidate(stages) or '—'}",
        ]
        self.query_one("#publish-detail-meta", Static).update("\n".join(meta))

        body = Text()
        body.append("Preflight\n", style=f"bold {brand.PALETTE['primary']}")
        for label, ok in checks:
            icon = brand.STATUS_ICONS["ok"] if ok else brand.STATUS_ICONS["warn"]
            color = brand.STATUS_COLORS["ok"] if ok else brand.STATUS_COLORS["warn"]
            body.append(f"{icon} {label}\n", style=color)
        if review is not None and review.report is not None:
            body.append("\nReview\n", style=f"bold {brand.PALETTE['primary']}")
            body.append(
                str(review.report.outcome) + "\n", style=brand.PALETTE["foreground"]
            )
        if qa is not None and qa.report is not None:
            body.append("\nQA\n", style=f"bold {brand.PALETTE['primary']}")
            body.append(
                str(qa.report.outcome) + "\n", style=brand.PALETTE["foreground"]
            )
        body.append(
            "\nTUI не открывает PR и не выполняет merge.\n",
            style=brand.PALETTE["muted"],
        )
        self.query_one("#publish-detail-body", Static).update(body)
        button = self.query_one("#publish-copy", Button)
        button.disabled = not bool(batch.pr_url)

    @on(ListView.Selected, "#publish-batches")
    def _batch_selected(self, event: ListView.Selected) -> None:
        if event.item.name:
            self._select(event.item.name)

    @on(Button.Pressed, "#publish-copy")
    def _copy_pr(self, event: Button.Pressed) -> None:
        batch = next(
            (
                item
                for item in (self._view.batches if self._view else [])
                if item.batch_id == self._selected
            ),
            None,
        )
        if batch is not None and batch.pr_url:
            self.app.copy_to_clipboard(batch.pr_url)
            self.app.notify("PR URL скопирован")

    @on(Button.Pressed, "#publish-refresh")
    def _refresh(self, event: Button.Pressed) -> None:
        event.stop()
        self._load()

    def action_refresh(self) -> None:
        self._load()

    def sync_language(self) -> None:
        if self._view is not None and self._selected is not None:
            self._select(self._selected)
