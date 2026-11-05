"""The recovery screen on the shared console shell: the batch history from the runtime store with a
lazily gated 'Open recovery' entry, then the recovery view of the selected batch. It keeps the
project, the selected batch, the breadcrumbs, the theme and the navigation of the shell. The reason
and the last confirmed boundary are drawn before any action; every action is an explicit button, an
unavailable one shows the core's reason, and nothing here abandons a batch or stops a worker."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, ListItem, ListView, Static

from .. import brand
from ..batch_history import BatchHistorySource, RecoveryEntry
from ..container_route import Action, Effect, mark
from ..coordinator_api import ArgvError
from ..recovery_view import (
    FixChoice,
    FixPreview,
    RecoverySession,
    RecoveryView,
    WizardTarget,
)
from ..runner import CommandRunner, capturing_runner
from ..shell import SHELL_CSS, ConsoleShell, ShellIds
from ..translate import Translated
from .commands import call_from_worker
from .container_route import ConfirmEffect, _t, render_body

MAX_ACTIONS = 8


class ChooseFix(Translated, ModalScreen[str | None]):
    """Fix never picks a value silently: the operator takes the core's normalization (a preview
    diff first) or edits the value at the pointer in the wizard."""

    BINDINGS = [Binding("escape", "cancel", "Отмена")]
    DEFAULT_CSS = """
    ChooseFix { align: center middle; }
    ChooseFix > Vertical { width: 80%; max-width: 90; height: auto; border: round $primary; padding: 1 2; background: $background; }
    ChooseFix Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Выберите способ исправления", id="fix-title")
            yield Button(
                "Нормализация ядра: сначала превью diff",
                id="fix-normalize",
                variant="primary",
            )
            yield Button("Выбрать значение в мастере настройки", id="fix-edit")
            yield Button("Отмена", id="fix-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(
            {
                "fix-normalize": FixChoice.NORMALIZE.value,
                "fix-edit": FixChoice.EDIT_AT_POINTER.value,
            }.get(event.button.id or "")
        )


class RecoveryScreen(ConsoleShell):
    """History of the store's batches, then recovery for the selected one."""

    SECTION = "Orchestration"
    IS_SECTION_ROOT = False
    CRUMBS = "Главная › Оркестрация › Восстановление"
    NARROW_FOOTER_KEYS = ("escape", "enter", "f2")
    IDS = ShellIds(
        navigation="recovery-navigation",
        menu="recovery-sections",
        content="recovery-content",
        breadcrumbs="recovery-breadcrumbs",
        toggle="recovery-menu",
        body="recovery-columns",
        context="recovery-context-panel",
    )
    CSS = SHELL_CSS + brand.shell_css("""
    RecoveryScreen #recovery-page { height: 1fr; padding: 0 2; }
    RecoveryScreen #recovery-title { height: 1; text-style: bold; margin-bottom: 1; }
    RecoveryScreen #recovery-history { height: 10; margin-bottom: 1; }
    RecoveryScreen #recovery-entry { height: auto; margin-bottom: 1; }
    RecoveryScreen #recovery-body { height: auto; padding: 0 1; border: round $component-border; }
    RecoveryScreen #recovery-actions { height: auto; margin-top: 1; }
    RecoveryScreen #recovery-actions Button { margin-right: 1; }
    RecoveryScreen #recovery-inputs { height: auto; margin-top: 1; }
    RecoveryScreen #recovery-inputs Input { width: 1fr; margin-right: 1; }
    RecoveryScreen #recovery-status { height: auto; margin-top: 1; }
    RecoveryScreen.-narrow #recovery-actions { layout: vertical; }
    RecoveryScreen.-narrow #recovery-inputs { layout: vertical; }
    RecoveryScreen.-narrow #recovery-inputs Input { width: 100%; margin-right: 0; }
    """)

    def __init__(
        self,
        repo: Path,
        *,
        batch: str = "",
        command_runner: CommandRunner = capturing_runner,
        source: BatchHistorySource | None = None,
    ) -> None:
        super().__init__()
        self.repo = repo
        self._command_runner = command_runner
        self.source = source or BatchHistorySource(repo, command_runner)
        self.batch_id = batch
        self.session: RecoverySession | None = None
        self._entry: RecoveryEntry | None = None
        self._busy = False
        self._status = ""
        self._action_keys: list[str] = []
        self._history_labels: list[tuple[Static, str]] = []

    @property
    def _language(self) -> str:
        return str(getattr(self.app, "language", "ru"))

    # ------------------------------------------------------------------ layout
    def compose_strip(self) -> ComposeResult:
        yield Static("", id="recovery-context", classes="no-i18n", markup=False)

    def compose_content(self) -> ComposeResult:
        with VerticalScroll(id="recovery-page"):
            yield Static("Восстановление batch", id="recovery-title")
            yield ListView(id="recovery-history")
            yield Static("", id="recovery-entry", classes="no-i18n", markup=False)
            with Horizontal(id="recovery-nav"):
                yield Button("Открыть recovery", id="recovery-open", disabled=True)
                yield Button("Обновить список", id="recovery-reload-list")
            yield Static("", id="recovery-body", classes="no-i18n", markup=False)
            with Horizontal(id="recovery-actions"):
                for slot in range(MAX_ACTIONS):
                    yield Button("", id=f"ract-{slot}", classes="no-i18n")
            with Horizontal(id="recovery-inputs"):
                yield Input(placeholder="approved-by", id="recovery-approver")
                yield Input(placeholder="note", id="recovery-note")
                yield Input(placeholder="ID диагностики", id="recovery-diagnostic")
            yield Static("", id="recovery-status", classes="no-i18n", markup=False)

    def on_mount(self) -> None:
        ConsoleShell.on_mount(self)
        Translated.on_mount(self)
        self._load_history()
        if self.batch_id:
            self._open(self.batch_id)
        else:
            self._refresh()

    def sync_language(self) -> None:
        ConsoleShell.sync_language(self)
        for widget, label in self._history_labels:
            widget.update(_t(self._language, label))
        self._refresh()

    # ------------------------------------------------------------------ data
    def _load_history(self) -> None:
        def work() -> None:
            history = self.source.reload()

            def show() -> None:
                if not self.is_mounted:
                    return
                listing = self.query_one("#recovery-history", ListView)
                listing.clear()
                self._history_labels = []
                if history.unavailable:
                    self._status = history.unavailable
                for item in history.batches:
                    widget = Static(
                        _t(self._language, item.label), markup=False, classes="no-i18n"
                    )
                    self._history_labels.append((widget, item.label))
                    listing.append(ListItem(widget, name=item.batch_id))
                if history.batches:
                    # Highlighting the newest batch asks the core about it, and only about it.
                    self.call_after_refresh(setattr, listing, "index", 0)
                self._refresh()

            call_from_worker(self, show)

        self.run_worker(work, thread=True, exclusive=True, group="recovery-history")

    @on(ListView.Highlighted, "#recovery-history")
    def _highlighted(self, event: ListView.Highlighted) -> None:
        name = event.item.name if event.item is not None else None
        if not name:
            return
        self.batch_choice = name

        def work() -> None:
            entry = self.source.recovery_entry(name)

            def show() -> None:
                self._entry = entry
                self._refresh()

            call_from_worker(self, show)

        self.run_worker(work, thread=True, exclusive=True, group="recovery-gate")

    batch_choice = ""

    def _open(self, batch: str) -> None:
        self.batch_id = batch
        self.session = RecoverySession(self.repo, batch, self._command_runner)
        self._status = ""
        self._run(self.session.refresh)

    # ------------------------------------------------------------------ drawing
    def _view(self) -> RecoveryView | None:
        return self.session.view() if self.session is not None else None

    def _actions(self, view: RecoveryView) -> list[Action]:
        actions = list(view.actions)
        preview: FixPreview | None = self.session.preview if self.session else None
        if preview is not None and preview.writable:
            actions.append(
                Action("fix-apply", "Записать нормализацию", True, "", Effect.DELETE)
            )
        return actions[:MAX_ACTIONS]

    def _refresh(self) -> None:
        if not self.is_mounted or not self.query("#recovery-body"):
            return
        language, narrow = self._language, self.has_class("-narrow")
        view = self._view()
        repo = str(self.repo)
        selected = self.batch_id or self.batch_choice
        self.query_one("#recovery-context", Static).update(
            f"{repo}  ·  {_t(language, 'batch')}: {selected or _t(language, 'не выбран')}"
        )
        entry = self._entry
        opener = self.query_one("#recovery-open", Button)
        opener.disabled = not (
            entry is not None and entry.enabled and entry.batch_id == self.batch_choice
        )
        self.query_one("#recovery-entry", Static).update(
            f"{mark(entry.state)}  {_t(language, entry.reason)}"
            if entry is not None
            else ""
        )
        if view is None:
            body = ""
            actions: list[Action] = []
        else:
            actions = self._actions(view)
            body = render_body(
                view.rows, view.blockers, view.notes, actions, language, narrow
            )
        self.query_one("#recovery-body", Static).update(body)
        self._action_keys = [action.key for action in actions]
        for slot in range(MAX_ACTIONS):
            button = self.query_one(f"#ract-{slot}", Button)
            if slot < len(actions):
                button.label = _t(language, actions[slot].label)
                button.disabled = not actions[slot].enabled or self._busy
                button.display = True
            else:
                button.display = False
        self.query_one("#recovery-status", Static).update(_t(language, self._status))

    # ------------------------------------------------------------------ input
    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "recovery-open":
            event.stop()
            if self.batch_choice:
                self._open(self.batch_choice)
        elif button_id == "recovery-reload-list":
            event.stop()
            self._load_history()
        elif button_id.startswith("ract-"):
            event.stop()
            slot = int(button_id.removeprefix("ract-"))
            if slot < len(self._action_keys):
                self._invoke(self._action_keys[slot])

    def _confirm(self, title: str, text: str, then) -> None:  # type: ignore[no-untyped-def]
        def decided(confirmed: bool | None) -> None:
            if confirmed:
                then()

        self.app.push_screen(ConfirmEffect(_t(self._language, title), text), decided)

    def _invoke(self, key: str) -> None:
        session, view = self.session, self._view()
        if session is None or view is None or self._busy:
            return
        action = next((a for a in self._actions(view) if a.key == key), None)
        if action is None:
            return
        if not action.enabled:
            self._status = f"✖ {action.reason}"
            self._refresh()
            return
        language = self._language
        if key == "status":
            self._run(session.refresh)
        elif key == "reload":
            self._run(session.reload, then_refresh=True)
        elif key == "fix":
            self.app.push_screen(ChooseFix(), self._fix_chosen)
        elif key == "fix-apply":
            self._confirm(
                "Подтвердите запись",
                _t(
                    language,
                    "Запись пойдёт через транзакцию конфигурации: проверка устаревания, резервная копия.",
                ),
                lambda: self._run(lambda: session.apply_fix(True), then_refresh=True),
            )
        elif key == "resume":
            plan = session.resume_plan()
            checks = ", ".join(f"{name}: {status}" for name, status in plan.checks)
            text = (
                f"{plan.command}\n{_t(language, 'проверки')}: {checks}\n"
                f"{_t(language, 'одобрение человека')}: {_t(language, 'нужно' if plan.approval_required else 'не требуется')}\n"
                f"{_t(language, 'дальше')}: {plan.next_step}"
            )
            approver = self.query_one("#recovery-approver", Input).value
            note = self.query_one("#recovery-note", Input).value
            self._confirm(
                "Подтвердите Resume",
                text,
                lambda: self._run(
                    lambda: session.resume(approver, note), then_refresh=True
                ),
            )
        elif key == "skip":
            diagnostic = self.query_one("#recovery-diagnostic", Input).value.strip()
            self._run(lambda: session.skip(diagnostic), then_refresh=True)
        elif key == "abort":
            self._confirm(
                "Подтвердите выход с сохранением",
                _t(
                    language,
                    "Выход с сохранением не отменяет batch, не останавливает worker и не очищает worktree.",
                ),
                lambda: self._run(session.abort),
            )

    def _fix_chosen(self, choice: str | None) -> None:
        session = self.session
        if session is None or choice is None:
            return
        if choice == FixChoice.NORMALIZE.value:
            self._run(lambda: session.fix(FixChoice.NORMALIZE))
            return
        diagnostic = self.query_one("#recovery-diagnostic", Input).value.strip()
        try:
            target = session.fix(FixChoice.EDIT_AT_POINTER, diagnostic)
        except ValueError as exc:
            self._status = f"✖ {exc}"
            self._refresh()
            return
        if isinstance(target, WizardTarget):
            from .configuration import ConfigurationScreen

            self.app.push_screen(
                ConfigurationScreen(self.repo, focus=(target.file, target.path)),
                lambda _: self._run(session.reload, then_refresh=True),
            )

    def _run(self, call, *, then_refresh: bool = False) -> None:  # type: ignore[no-untyped-def]
        """Runs one session call in a worker thread; the status is read again afterwards when the
        action changed something the screen shows."""
        session = self.session
        if session is None:
            return
        self._busy = True
        self._status = _t(self._language, "Выполняется…")
        self._refresh()

        def work() -> None:
            status = ""
            try:
                call()
                if then_refresh:
                    session.refresh()
            except (PermissionError, ValueError, ArgvError) as exc:
                status = f"✖ {exc}"

            def done() -> None:
                self._busy = False
                self._status = status
                self._refresh()

            call_from_worker(self, done)

        self.run_worker(work, thread=True, exclusive=True, group="recovery")
