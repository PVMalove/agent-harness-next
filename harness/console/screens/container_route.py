"""The container executor route on the shared console shell: executor context strip, six stage tabs
that only switch the pane, and one explicit button per external effect. Choosing a tab or moving
focus never runs a command, grants an approval or bypasses a gate; an action that cannot run shows
its reason. All state comes from `harness.console.container_route`, which asks the coordinator CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import brand, i18n
from ..container_route import (
    Action,
    Effect,
    RouteSession,
    Row,
    Stage,
    StageView,
    Tab,
    mark,
)
from ..coordinator_api import ArgvError
from ..runner import CommandRunner, capturing_runner
from ..shell import SHELL_CSS, ConsoleShell, ShellIds
from ..translate import Translated
from .commands import call_from_worker


def _t(language: str, text: str) -> str:
    return i18n.tr_text(language, text)


def render_row(row: Row, language: str, narrow: bool) -> str:
    """`✔ ок  Label: value`; a multi-line value continues indented. On a narrow terminal the value
    starts on its own line, so a long ID, path or digest wraps instead of being cut."""
    status = _t(language, mark(row.state)) if row.state is not None else ""
    label = _t(language, row.label)
    value = _t(language, row.value)
    lines = value.split("\n") if value else []
    head = f"{status}  {label}".strip() if status else label
    if narrow:
        return "\n".join([head, *(f"    {line}" for line in lines)])
    if not lines:
        return head
    pad = " " * 4
    return "\n".join([f"{head}: {lines[0]}", *(f"{pad}{line}" for line in lines[1:])])


def render_actions(actions: Sequence[Action], language: str) -> list[str]:
    """Every action that cannot run, with its reason: nothing is silently greyed out."""
    return [
        f"{_t(language, '✖ недоступно')}: {_t(language, action.label)} — {_t(language, action.reason)}"
        for action in actions
        if not action.enabled and action.reason
    ]


def render_body(
    rows: Sequence[Row],
    blockers: Sequence[str],
    notes: Sequence[str],
    actions: Sequence[Action],
    language: str,
    narrow: bool,
) -> str:
    """The whole text of a pane: blockers first, then facts by group, unavailable actions, notes.
    Values are never shortened; the pane scrolls."""
    parts: list[str] = []
    if blockers:
        parts.append(_t(language, "✖ Блокирует маршрут"))
        parts.extend(
            f"  {line}"
            for blocker in blockers
            for line in _t(language, blocker).split("\n")
        )
        parts.append("")
    group = None
    for row in rows:
        if row.group != group:
            group = row.group
            if group:
                parts.append(_t(language, group).upper())
        parts.append(render_row(row, language, narrow))
    unavailable = render_actions(actions, language)
    if unavailable:
        parts.append("")
        parts.extend(unavailable)
    if notes:
        parts.append("")
        parts.extend(_t(language, note) for note in notes)
    return "\n".join(parts)


def render_view(view: StageView, language: str, narrow: bool) -> str:
    return render_body(
        view.rows, view.blockers, view.notes, view.actions, language, narrow
    )


def tab_label(tab: Tab, language: str, current: bool) -> str:
    """`✔ Preflight`: the state icon and the title; the current tab is bracketed."""
    icon = mark(tab.state).split(" ")[0]
    title = _t(language, tab.title)
    return f"[{icon} {title}]" if current else f"{icon} {title}"


def context_text(context: Sequence[tuple[str, str]], language: str) -> str:
    return "  ·  ".join(
        f"{_t(language, label)}: {_t(language, value)}" for label, value in context
    )


class ConfirmEffect(Translated, ModalScreen[bool]):
    """Names what an action will do; only an explicit Confirm runs it, Escape cancels."""

    BINDINGS = [Binding("escape", "cancel", "Отмена")]
    DEFAULT_CSS = """
    ConfirmEffect { align: center middle; }
    ConfirmEffect > Vertical { width: 80%; max-width: 90; height: auto; border: round $primary; padding: 1 2; background: $background; }
    ConfirmEffect .actions { height: auto; margin-top: 1; }
    """

    def __init__(self, title: str, text: str) -> None:
        super().__init__()
        self.title_text = title
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.title_text, id="confirm-title")
            yield Static(self.text, id="confirm-text", markup=False, classes="no-i18n")
            with Horizontal(classes="actions"):
                yield Button("Подтвердить", id="confirm-yes", variant="primary")
                yield Button("Отмена", id="confirm-no")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "confirm-yes")


MAX_ACTIONS = 4

_EFFECT_TITLES = {
    Effect.APPROVE: "Подтвердите одобрение",
    Effect.RUN: "Подтвердите запуск",
    Effect.DELETE: "Подтвердите удаление",
}


class ContainerRouteScreen(ConsoleShell):
    """Setup, Preflight, Plan / approval, Worker, QA and Cleanup of one container dispatch."""

    SECTION = "Orchestration"
    IS_SECTION_ROOT = False
    CRUMBS = "Главная › Оркестрация › Контейнерный маршрут"
    NARROW_FOOTER_KEYS = ("escape", "enter", "f2")
    IDS = ShellIds(
        navigation="route-navigation",
        menu="route-sections",
        content="route-content",
        breadcrumbs="route-breadcrumbs",
        toggle="route-menu",
        body="route-columns",
        context="route-context-panel",
    )
    CSS = SHELL_CSS + brand.shell_css("""
    ContainerRouteScreen #route-page { height: 1fr; padding: 0 2; }
    ContainerRouteScreen #route-title { height: 1; text-style: bold; margin-bottom: 1; }
    ContainerRouteScreen #route-select { height: auto; margin-bottom: 1; }
    ContainerRouteScreen #route-select Input { width: 1fr; margin-right: 1; }
    ContainerRouteScreen #route-tabs { height: auto; margin-bottom: 1; }
    ContainerRouteScreen #route-tabs Button { margin-right: 1; }
    ContainerRouteScreen #route-tab-reason { height: auto; color: $text-muted; margin-bottom: 1; }
    ContainerRouteScreen #route-body { height: auto; padding: 0 1; border: round $component-border; }
    ContainerRouteScreen #route-actions { height: auto; margin-top: 1; }
    ContainerRouteScreen #route-actions Button { margin-right: 1; }
    ContainerRouteScreen #route-approver { margin-top: 1; }
    ContainerRouteScreen #route-status { height: auto; margin-top: 1; }
    ContainerRouteScreen.-narrow #route-select { layout: vertical; }
    ContainerRouteScreen.-narrow #route-select Input { width: 100%; margin-right: 0; }
    ContainerRouteScreen.-narrow #route-tabs { layout: vertical; }
    ContainerRouteScreen.-narrow #route-actions { layout: vertical; }
    """)

    def __init__(
        self,
        repo: Path,
        *,
        batch: str = "",
        command_runner: CommandRunner = capturing_runner,
        session: RouteSession | None = None,
    ) -> None:
        super().__init__()
        self.repo = repo
        self._command_runner = command_runner
        self.session = session or RouteSession(repo, command_runner)
        if batch:
            self.session.select(batch)
        self.stage = Stage.SETUP
        self._busy = False
        self._status = ""
        self._action_keys: list[str] = []

    # ------------------------------------------------------------------ layout
    @property
    def _language(self) -> str:
        return str(getattr(self.app, "language", "ru"))

    def _narrow(self) -> bool:
        return self.has_class("-narrow")

    def compose_strip(self) -> ComposeResult:
        yield Static("", id="route-context", classes="no-i18n", markup=False)

    def compose_content(self) -> ComposeResult:
        selection = self.session.selection
        with VerticalScroll(id="route-page"):
            yield Static("Контейнерный маршрут", id="route-title")
            with Horizontal(id="route-select"):
                yield Input(selection.batch, placeholder="batch", id="route-batch")
                yield Input(selection.role, placeholder="role", id="route-role")
                yield Input(
                    selection.runtime, placeholder="runtime", id="route-runtime"
                )
                yield Button("Выбрать", id="route-choose")
            with Horizontal(id="route-tabs"):
                for stage in Stage:
                    yield Button("", id=f"tab-{stage.value}", classes="no-i18n")
            yield Static("", id="route-tab-reason", classes="no-i18n", markup=False)
            yield Static("", id="route-body", classes="no-i18n", markup=False)
            with Horizontal(id="route-actions"):
                # A fixed pool: a stage shows at most MAX_ACTIONS buttons, the rest stay hidden.
                for slot in range(MAX_ACTIONS):
                    yield Button("", id=f"act-{slot}", classes="no-i18n")
            yield Input(placeholder="approved-by", id="route-approver")
            yield Static("", id="route-status", classes="no-i18n", markup=False)

    def on_mount(self) -> None:
        ConsoleShell.on_mount(self)
        Translated.on_mount(self)
        self._refresh()

    def sync_language(self) -> None:
        ConsoleShell.sync_language(self)
        self._refresh()

    # ------------------------------------------------------------------ drawing
    def _current_tab(self) -> Tab:
        return next(tab for tab in self.session.tabs() if tab.stage is self.stage)

    def _refresh(self) -> None:
        """Redraw from the session. Drawing runs no command."""
        if not self.is_mounted or not self.query("#route-body"):
            return
        language = self._language
        narrow = self._narrow()
        view = self.session.view(self.stage)
        for tab in self.session.tabs():
            button = self.query_one(f"#tab-{tab.stage.value}", Button)
            button.label = tab_label(tab, language, tab.stage is self.stage)
        reason = self._current_tab().reason
        self.query_one("#route-tab-reason", Static).update(_t(language, reason))
        self.query_one("#route-body", Static).update(
            render_view(view, language, narrow)
        )
        self.query_one("#route-context", Static).update(
            context_text(self.session.executor_context(), language)
        )
        self.query_one("#route-status", Static).update(self._status)
        self._action_keys = [action.key for action in view.actions]
        for slot in range(MAX_ACTIONS):
            button = self.query_one(f"#act-{slot}", Button)
            if slot < len(view.actions):
                action = view.actions[slot]
                button.label = _t(language, action.label)
                button.disabled = not action.enabled or self._busy
                button.display = True
            else:
                button.display = False
        self.query_one("#route-approver", Input).display = any(
            action.effect is Effect.APPROVE for action in view.actions
        )

    def on_resize(self, event: object) -> None:
        super().on_resize(event)  # type: ignore[arg-type]
        self.call_after_refresh(self._refresh)

    # ------------------------------------------------------------------ input
    @on(Button.Pressed)
    def _pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("tab-"):
            event.stop()
            self.stage = Stage(button_id.removeprefix("tab-"))
            self._status = ""
            self._refresh()  # a tab only switches the pane
        elif button_id == "route-choose":
            event.stop()
            self.session.select(
                self.query_one("#route-batch", Input).value,
                self.query_one("#route-role", Input).value,
                self.query_one("#route-runtime", Input).value,
            )
            self._status = ""
            self._refresh()
        elif button_id.startswith("act-"):
            event.stop()
            slot = int(button_id.removeprefix("act-"))
            if slot < len(self._action_keys):
                self._invoke(self._action_keys[slot])

    def _action(self, key: str) -> Action | None:
        return next(
            (a for a in self.session.view(self.stage).actions if a.key == key), None
        )

    def _invoke(self, key: str) -> None:
        action = self._action(key)
        if action is None or self._busy:
            return
        language = self._language
        if not action.enabled:
            self._status = f"✖ {_t(language, action.reason)}"
            self._refresh()
            return
        if action.needs_confirmation:
            title = _t(
                language, _EFFECT_TITLES.get(action.effect, "Подтвердите действие")
            )
            text = (
                f"{_t(language, action.label)}\n{_t(language, self._effect_text(key))}"
            )

            def decided(confirmed: bool | None) -> None:
                if confirmed:
                    self._execute(key)

            self.app.push_screen(ConfirmEffect(title, text), decided)
            return
        self._execute(key)

    def _effect_text(self, key: str) -> str:
        return {
            "approve": "Одобрение привяжется к показанному transition_digest.",
            "qa-approve": "Одобрение QA привяжется к его собственному transition_digest.",
            "qa-run": "Gate-команды выполнятся в контейнере; ядро может принять результат по политике.",
            "send": "Откроется форма dispatch send; worker стартует только после её подтверждения.",
            "cleanup-apply": "Будет удалён весь показанный план, включая не контейнерные пункты.",
        }.get(key, "Действие меняет состояние вне консоли.")

    def _methods(self) -> dict[str, Callable[[], object]]:
        approver = self.query_one("#route-approver", Input).value
        session = self.session
        return {
            "recheck": session.recheck,
            "propose": session.propose,
            "approve": lambda: session.create(approver),
            "refresh": session.refresh_worker,
            "qa-propose": session.propose_qa,
            "qa-approve": lambda: session.create_qa(approver),
            "qa-run": session.run_qa,
            "qa-status": session.refresh_qa,
            "cleanup-preview": session.preview_cleanup,
            "cleanup-apply": session.apply_cleanup,
        }

    def _execute(self, key: str) -> None:
        if key == "edit-config":
            self._open_wizard()
            return
        if key == "send":
            self._open_send()
            return
        call = self._methods().get(key)
        if call is None:
            return
        self._busy = True
        self._status = _t(self._language, "Выполняется…")
        self._refresh()

        def work() -> None:
            status = ""
            try:
                call()
            except (PermissionError, ValueError, ArgvError) as exc:
                status = f"✖ {exc}"

            def done() -> None:
                self._busy = False
                self._status = status
                self._refresh()

            call_from_worker(self, done)

        self.run_worker(work, thread=True, exclusive=True, group="route")

    def _open_wizard(self) -> None:
        from .configuration import ConfigurationScreen

        self.app.push_screen(
            ConfigurationScreen(
                self.repo, focus=("orchestration.json", ("access_policy",))
            )
        )

    def _open_send(self) -> None:
        from ..coordinator_catalog import COORDINATOR_COMMANDS, process_argv
        from .orchestration import CoordinatorCommandFormScreen
        from .worker_observation import WorkerObservationScreen

        entry = next(
            item for item in COORDINATOR_COMMANDS if item.key == "dispatch-send"
        )
        dispatch = self.session.selection.dispatch
        repo = self.repo

        def launched(values: "dict[str, str] | None") -> None:
            if values is None:
                return
            screen = WorkerObservationScreen(repo, dispatch)
            self.app.push_screen(screen)
            self.app.call_after_refresh(
                screen.launch,
                process_argv(entry.cli_argv(repo, values)),
                self._command_runner,
            )

        form = CoordinatorCommandFormScreen(entry, repo)
        self.app.push_screen(form, launched)
