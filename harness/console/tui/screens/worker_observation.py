"""Live local worker view in the shared Harness console; observation never prompts a model."""

from __future__ import annotations

import argparse
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rich.cells import cell_len
from rich.columns import Columns
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import (
    Button,
    OptionList,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from harness.orchestration.core.utils import JsonObject
from ...kernel import brand, i18n
from ...kernel import reports
from ...kernel.execution_facts import ExecutionSummary, observe_execution
from ..chrome import TopBar
from ...kernel.runner import CommandRunner
from .. import icons
from ..client import WorkerSteps
from ..session_card import session_card, status_caption
from ...kernel.status import PERMISSION_PENDING, process_status, session_status
from ..crumbs import Crumb
from ..shell import (
    HOME_SECTION,
    SHELL_CSS,
    Breadcrumbs,
    ConsoleShell,
    SeparatorWrap,
    ShellIds,
    WrappedValue,
)
from ..translate import Translated
from ..widgets import LiveDot
from ..wrap import wrap_value
from .commands import call_from_worker

Observer = Callable[[Path, str, int], JsonObject]
StepsReader = Callable[[str, int], WorkerSteps | None]

# Why the transcript is unavailable; the worker outcome never depends on it.
STEP_REASONS = {
    "no_log": "worker не предоставил наблюдаемый лог",
    "log_missing": "лог worker ещё не создан",
    "log_unreadable": "лог worker не читается",
    "log_outside_storage": "лог worker вне хранилища harness",
    "log_unrecognised": "формат лога worker не распознан, текст не показывается",
    "qa_on_host": "QA идёт на хосте: результаты стадий появятся после прогона",
    "no_dispatch": "ledger не знает этот dispatch",
    "no_server": "нет соединения с сервером консоли",
}
_OBSERVER_STREAM = frozenset(
    {
        "events",
        "next_offset",
        "reset",
        "stream_state",
        "stream_reason",
        "last_event_age_seconds",
    }
)


# The console server may hold its one connection for minutes (online checks of another screen):
# the poll waits this long for its page and then follows the observer's own reading of the log.
STEPS_WAIT_SECONDS = 1.0
# A poll that has not answered for this long is reported instead of leaving the initial view.
POLL_STALL_SECONDS = 10.0
_OBSERVED = frozenset({"connected", "waiting"})


def with_server_steps(
    snapshot: JsonObject, steps: WorkerSteps | None, failure: str
) -> JsonObject:
    """The process facts of `snapshot` with the transcript of the console server; the observer's
    own events are dropped. Without a page the observer's events are the transcript when it reads
    the worker log; otherwise the transcript is unavailable for `failure`."""
    facts: JsonObject = {
        key: value for key, value in snapshot.items() if key not in _OBSERVER_STREAM
    }
    from harness.orchestration.workflow.delivery import IN_PROCESS_STREAM_REASON

    # An in-process dispatch has no stream at all: its reason is a fact of the dispatch.
    if snapshot.get("stream_reason") == IN_PROCESS_STREAM_REASON:
        facts["stream_reason"] = IN_PROCESS_STREAM_REASON
    if steps is None and snapshot.get("stream_state") in _OBSERVED:
        return {**snapshot, "steps_source": "observer"}
    if steps is None:
        return {
            **facts,
            "events": [],
            "reset": False,
            "stream_state": "unavailable",
            "steps_reason": failure,
            "steps_structure": "unavailable",
        }
    return {
        **facts,
        "events": [{"kind": kind, "text": text} for kind, text in steps.steps],
        "next_offset": steps.offset,
        "reset": steps.reset,
        "stream_state": steps.state,
        "steps_reason": steps.reason,
        "steps_source": steps.source,
        "steps_structure": steps.structure,
        "last_event_age_seconds": steps.last_step_age_seconds,
    }


@dataclass(frozen=True)
class Poll:
    """One observation of a dispatch: the snapshot to show, where the observer reads next, and why
    the server transcript is not used (None while the server answers)."""

    snapshot: JsonObject
    observer_offset: int
    steps_failure: str | None


def bounded_steps(
    reader: StepsReader | None, dispatch: str, offset: int
) -> tuple[WorkerSteps | None, str]:
    """The server page of `dispatch`, or None with why: no client, an error, no such dispatch, or
    no reply within `STEPS_WAIT_SECONDS`. A late reply is dropped; its thread ends on its own."""
    if reader is None:
        return None, "no_server"
    found: list[WorkerSteps | None] = []

    def read() -> None:
        try:
            found.append(reader(dispatch, offset))
        except Exception:
            pass  # Any failure of the server read leaves the observer's own stream.

    thread = threading.Thread(target=read, name="worker-steps", daemon=True)
    thread.start()
    thread.join(STEPS_WAIT_SECONDS)
    if not found:
        return None, "no_server"
    return found[0], "no_dispatch"


def poll_worker(
    repo: Path,
    dispatch: str,
    observer: Observer,
    reader: StepsReader | None,
    *,
    observer_offset: int,
    server_offset: int,
    steps_failure: str | None,
) -> Poll:
    """Observe `dispatch` once. After the server failed to give a page (`steps_failure`), it is
    not asked again: the transcript follows the observer, so no step is shown twice."""
    try:
        snapshot = observer(repo, dispatch, observer_offset)
        if steps_failure is None:
            steps, failure = bounded_steps(reader, dispatch, server_offset)
        else:
            steps, failure = None, steps_failure
        shown = with_server_steps(snapshot, steps, failure)
    except Exception:
        return Poll(
            {"dispatch_id": dispatch, "observation_error": True},
            observer_offset,
            steps_failure,
        )
    following = snapshot.get("next_offset", observer_offset)
    return Poll(
        shown,
        following if isinstance(following, int) else observer_offset,
        failure if steps is None else None,
    )


class PollGate:
    """One poll per view generation at a time; a poll running longer than `POLL_STALL_SECONDS`
    is stalled. A poll of an earlier generation (another session, a reconnect) blocks nothing."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._running: int | None = None
        self._started = 0.0

    def begin(self, generation: int) -> bool:
        if self._running == generation:
            return False
        self._running, self._started = generation, self._clock()
        return True

    def finish(self, generation: int) -> None:
        if self._running == generation:
            self._running = None

    def stalled(self, generation: int) -> bool:
        return (
            self._running == generation
            and self._clock() - self._started >= POLL_STALL_SECONDS
        )


@dataclass(frozen=True)
class Sessions:
    """The session list: the stage of each dispatch, the batches with a timeline, and the
    `(label, dispatch)` choices, running sessions first, newest first."""

    stages: dict[str, reports.StageEntry]
    batches: frozenset[str]
    choices: list[tuple[str, str]]


def session_choices(view: reports.LedgerView, dispatch: str | None) -> Sessions:
    """The sessions of `view`; a requested `dispatch` the ledger does not list comes first."""
    ordered = sorted(view.stages, key=lambda stage: stage.at, reverse=True)
    ordered.sort(key=lambda stage: stage.finished)
    choices = [
        (f"{stage.ticket} · {stage.role}", stage.dispatch_id) for stage in ordered
    ]
    if dispatch and not any(value == dispatch for _, value in choices):
        choices.insert(0, (dispatch, dispatch))
    return Sessions(
        {stage.dispatch_id: stage for stage in ordered},
        frozenset(batch.batch_id for batch in view.batches),
        choices,
    )


def session_options(
    choices: list[tuple[str, str]], card: Callable[[str, str], Text]
) -> list[Option | None]:
    """One option per session with its card, a separator after each; the option id is the
    dispatch. One list widget draws them all, so a long ledger mounts no widget per session."""
    options: list[Option | None] = []
    for label, dispatch in choices:
        options += [Option(card(label, dispatch), id=dispatch), None]
    return options


# The runtime reconciles an execution it is asked about, and the ledger view is read whole: both
# are asked less often than the worker log (#1296).
EXECUTION_SECONDS = 5.0
# Below this terminal width the session list is narrower, so the main pane keeps its action bar.
TIGHT_WIDTH = 160
TIMELINE_SECONDS = 10.0
TIMELINE_LIMIT = 40


def execution_lines(summary: ExecutionSummary | None, t: Callable[[str], str]) -> list[str]:
    """What the runtime observes of the session's execution, one fact per line (#1296)."""
    if summary is None:
        return [t("Runtime не надзирает за этим dispatch или не ответил.")]
    none = t("не сообщается")
    kind = t("Контейнер worker") if summary.kind == "container" else t("Процесс worker")
    exit_parts = [
        f"{t('код')} {summary.exit_code}" if summary.exit_code is not None else "",
        f"{t('остановлено')}: {summary.stopped_by}" if summary.stopped_by else "",
        t("нехватка памяти (OOM)") if summary.oom_killed else "",
    ]
    exit_text = " · ".join(part for part in exit_parts if part) or t("ещё не завершилось")
    teardown = (
        t("объекты удалены")
        if summary.teardown == "removed"
        else summary.teardown or t("ещё не выполнялась")
    )
    lines = [
        f"{kind}: {summary.state or none}",
        f"{t('Движок')}: {summary.engine or none}",
        f"{t('Образ')}: {summary.image or none}",
    ]
    if summary.container_id:
        lines.append(f"{t('ID контейнера')}: {summary.container_id[:12]}")
    lines += [
        f"{t('Дедлайн')}: {summary.deadline or none}",
        f"{t('Наблюдалось')}: {summary.observed_at or none}",
        f"{t('Завершение')}: {exit_text}",
        f"{t('Очистка')}: {teardown}",
    ]
    if summary.stderr_tail:
        lines.append(t("Последние строки stderr") + ":")
        lines += [f"  {line}" for line in summary.stderr_tail]
    return lines


# What the observer knows of the worker process: glyph, Russian and English words, colour.
_PROCESS_WORDS = {
    "live": ("►", "процесс работает", "process running", "success"),
    "stopped": (icons.STOP, "процесс завершён", "process exited", "muted"),
    "absent": (icons.STATUS_ICONS["skipped"], "процесс не найден", "process not found", "warning"),
}
# The state of the worker's event stream: Russian and English words and colour.
_STREAM_WORDS = {
    "connected": ("поток подключён", "stream connected", "success"),
    "waiting": ("поток ждёт событий", "stream waiting for events", "muted"),
    "unavailable": ("поток недоступен", "stream unavailable", "warning"),
}


def process_line(snapshot: JsonObject, worker: str, language: str) -> Text:
    """The process, the ledger state and the event stream in words, each in its colour."""
    en = language == "en"
    glyph, ru_word, en_word, colour = _PROCESS_WORDS.get(
        worker, (icons.UNKNOWN, "процесс не наблюдается", "process not observed", "muted")
    )
    line = Text(f"{glyph} {en_word if en else ru_word}", style=brand.PALETTE[colour])
    state = session_status(str(snapshot.get("state") or "unknown"))
    line.append(" · ledger ", style=brand.PALETTE["muted"])
    line.append(icons.render_status(state, language), style=state.color)
    stream = str(snapshot.get("stream_state") or "")
    ru_stream, en_stream, stream_colour = _STREAM_WORDS.get(
        stream, (f"поток: {stream or '—'}", f"stream: {stream or '—'}", "muted")
    )
    reason = snapshot.get("stream_reason")
    line.append(" · ", style=brand.PALETTE["muted"])
    line.append(
        (en_stream if en else ru_stream) + (f" ({reason})" if reason else ""),
        style=brand.PALETTE[stream_colour],
    )
    return line


def heartbeat_line(snapshot: JsonObject, language: str) -> Text:
    """The last heartbeat as a UTC time and the age of the last event in words."""
    en = language == "en"
    beat = reports.timestamp(str(snapshot.get("heartbeat_at") or ""))
    line = Text("heartbeat ", style=brand.PALETTE["muted"])
    line.append(
        beat.strftime("%d.%m.%Y %H:%M:%S UTC")
        if beat
        else ("not observed" if en else "не наблюдался"),
        style=brand.PALETTE["foreground" if beat else "muted"],
    )
    age = snapshot.get("last_event_age_seconds")
    line.append(" · ", style=brand.PALETTE["muted"])
    if isinstance(age, int | float) and not isinstance(age, bool):
        line.append(
            f"event {int(age)} s ago" if en else f"событие {int(age)} с назад",
            style=brand.PALETTE["foreground"],
        )
    else:
        line.append("no events yet" if en else "событий ещё нет", style=brand.PALETTE["muted"])
    return line


def _status_colour(line: str) -> str:
    """The colour of a status note by its leading symbol: ▲ warning, ■ error, others muted."""
    return brand.PALETTE[
        "warning"
        if line.startswith((icons.STATUS_ICONS["warn"], "⚠"))
        else "error"
        if line.startswith((icons.STATUS_ICONS["fail"], "✖"))
        else "muted"
    ]


def timeline_rows(
    timeline: reports.BatchTimeline | None, limit: int = TIMELINE_LIMIT
) -> list[tuple[str, str, str, str]]:
    """The newest orchestration events of the batch, oldest first: time, kind, role and text."""
    if timeline is None:
        return []
    return [
        (event.at[11:19] or "--:--:--", event.kind, event.role or "-", event.text)
        for event in timeline.events[-limit:]
    ]


def timeline_table(rows: list[tuple[str, str, str, str]]) -> Table:
    """The timeline as a grid: an event's text wraps inside its own column, so the time, kind and
    role columns stay aligned on a narrow main column. The kind and the role are icons in their
    colours; `timeline_legend` names them."""
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(no_wrap=True, style=brand.PALETTE["muted"])
    table.add_column(width=1, no_wrap=True)
    table.add_column(width=1, no_wrap=True)
    table.add_column(ratio=1, overflow="fold")
    for at, kind, role, text in rows:
        kind_glyph, kind_colour = icons.timeline_icon(kind)
        role_glyph, role_colour = icons.role_icon(role)
        table.add_row(
            at,
            Text(kind_glyph, style=f"bold {kind_colour}"),
            Text(role_glyph, style=f"bold {role_colour}"),
            SeparatorWrap(brand.short_dispatch(text)),
        )
    return table


def timeline_legend(rows: list[tuple[str, str, str, str]], language: str = "ru") -> Text:
    """The kinds and then the roles of the shown events, each as its icon and word, under the
    timeline."""
    legend = icons.kinds_legend((kind for _at, kind, _role, _text in rows), language)
    for role in dict.fromkeys(role for _at, _kind, role, _text in rows):
        glyph, colour = icons.role_icon(role)
        if glyph:
            legend.append("   ")
            legend.append(glyph, style=f"bold {colour}")
            legend.append(f" {role}", style=brand.PALETTE["muted"])
    return legend


# An event kind's glyph, Russian and English label and colour on the «События» tab. Each glyph
# is a shape of its own in its own colour, drawn as a chip, so the kinds differ at a glance; an
# unknown kind is shown with the `system` look and its own name.
EVENT_KINDS: dict[str, tuple[str, str, str, str]] = {
    "output":       ("›", "вывод",       "output",       brand.PALETTE["foreground"]),
    "tool":         ("♦", "инструмент",  "tool",         brand.PALETTE["primary"]),
    "tool-result":  ("◦", "результат",   "result",       brand.PALETTE["muted"]),
    "result":       (icons.STATUS_ICONS["ok"], "итог",        "outcome",      brand.PALETTE["success"]),
    "error":        (icons.STATUS_ICONS["fail"], "ошибка",      "error",        brand.PALETTE["error"]),
    "stderr":       (icons.STATUS_ICONS["warn"], "stderr",      "stderr",       brand.PALETTE["warning"]),
    "permission":   ("◊", "разрешение",  "permission",   brand.PALETTE["warning"]),
    "stage":        (icons.STATUS_KIND_ICONS["running"], "стадия QA",   "QA stage",     brand.PALETTE["primary"]),
    "stage-result": (icons.STATUS_ICONS["ok"], "итог стадии", "stage result", brand.PALETTE["foreground"]),
    "log":          (icons.PLAIN_LOG, "лог",         "log",          brand.PALETTE["muted"]),
    "system":       ("▪", "система",     "system",       brand.PALETTE["muted"]),
    "omitted":      ("▫", "пропущено",   "omitted",      brand.PALETTE["muted"]),
}
# The glyph of a finished QA stage follows its result, as `_stage_result` words it.
_STAGE_RESULTS = {
    "pass":    (icons.STATUS_ICONS["ok"], brand.PALETTE["success"]),
    "fail":    (icons.STATUS_ICONS["fail"], brand.PALETTE["error"]),
    "not_run": (icons.STATUS_ICONS["skipped"], brand.PALETTE["muted"]),
}
CHIP_WIDTH = 3


def _event_look(kind: str, text: str, language: str) -> tuple[str, str, str]:
    glyph, ru, en, colour = EVENT_KINDS.get(kind, (icons.UNKNOWN, kind, kind, brand.PALETTE["muted"]))
    if kind == "stage-result":
        words = text.partition(":")[2].split()
        glyph, colour = _STAGE_RESULTS.get(words[0] if words else "", (glyph, colour))
    return glyph, en if language == "en" else ru, colour


def _chip(glyph: str, colour: str) -> Text:
    """A glyph as a three-cell chip on a tinted ground, so it reads larger than a bare symbol."""
    return Text(
        f" {glyph} ",
        style=f"bold {colour} on {brand.SHELL_TOKENS['event-active-background']}",
    )


# The «Сессия» tab reads as Claude CLI: a message or a tool call is a ● line after a blank line,
# and what it returned hangs under it on └. A tool call shows only the tool's name: the kernel never
# passes tool inputs (`visible_events`). The colour of each kind's ●:
_BULLETS: dict[str, str] = {
    "output": brand.PALETTE["foreground"],
    "tool": brand.PALETTE["success"],
    "result": brand.PALETTE["success"],
    "error": brand.PALETTE["error"],
    "permission": brand.PALETTE["warning"],
    "stage": brand.PALETTE["primary"],
    "system": brand.PALETTE["muted"],
}
# A tool result folds to its first lines until `expanded`, as Claude CLI does until ctrl+o.
RESULT_LINES = 5
# A numbered line of a Read result: `   45<TAB>text` or `   45→text`.
_NUMBERED = re.compile(r"^\s*(\d+)(?:\t|→)(.*)$")
# A result that holds a unified diff marks its added and removed lines.
_DIFF_START = re.compile(r"^(?:@@ |diff --git |\+\+\+ |--- )")
# `└` is a box-drawing corner every monospace font carries (the terminal draws it itself), not
# Claude CLI's `⎿`, which comes from a fallback font of another size.
_RESULT_PREFIX = "  └  "


def _bullet(kind: str, text: str) -> RenderableType:
    colour = _BULLETS.get(kind, brand.PALETTE["muted"])
    style = {
        "tool": f"bold {brand.PALETTE['foreground']}",
        "error": brand.PALETTE["error"],
        "system": brand.PALETTE["muted"],
        "omitted": brand.PALETTE["muted"],
    }.get(kind, brand.PALETTE["foreground"])
    row = Table.grid(expand=True)
    row.add_column(width=2, no_wrap=True)
    row.add_column(ratio=1, overflow="fold")
    row.add_row(
        Text("●", style=f"bold {colour}"), SeparatorWrap(Text(text, style=style))
    )
    return Group(Text(""), row)


def _line_style(line: str, diff: bool, default: str) -> str:
    if diff and line.startswith("+") and not line.startswith("+++"):
        return brand.PALETTE["success"]
    if diff and line.startswith("-") and not line.startswith("---"):
        return brand.PALETTE["error"]
    if diff and line.startswith("@@"):
        return brand.PALETTE["primary"]
    return default


def _result(kind: str, text: str, language: str, expanded: bool) -> RenderableType:
    """What a call returned, under └: numbered code keeps its numbers in a muted column, a diff
    marks its lines, and a long result shows its first lines with the count of the rest."""
    muted = brand.PALETTE["muted"]
    default = {
        "stderr": brand.PALETTE["warning"],
        "stage-result": brand.PALETTE["foreground"],
    }.get(kind, muted)
    lines = text.splitlines() or [""]
    numbered = [_NUMBERED.match(line) for line in lines]
    code = sum(match is not None for match in numbered) * 2 >= len(lines)
    diff = any(_DIFF_START.match(line) for line in lines)
    shown = len(lines) if expanded or len(lines) <= RESULT_LINES else RESULT_LINES
    grid = Table.grid(expand=True)
    grid.add_column(width=len(_RESULT_PREFIX), no_wrap=True)
    if code:
        digits = max(len(match.group(1)) for match in numbered if match)
        grid.add_column(width=digits, no_wrap=True, justify="right")
        grid.add_column(width=2, no_wrap=True)
    grid.add_column(ratio=1, overflow="fold")
    for index, (line, match) in enumerate(zip(lines[:shown], numbered[:shown])):
        prefix = Text(_RESULT_PREFIX if index == 0 else "", style=muted)
        if kind == "stage-result" and index == 0:
            words = line.partition(":")[2].split()
            glyph, colour = _STAGE_RESULTS.get(words[0] if words else "", (icons.STATUS_ICONS["skipped"], muted))
            body = Text(f"{glyph} ", style=colour)
            body.append(line, style=default)
        elif code:
            body = Text(
                match.group(2) if match else line, style=brand.PALETTE["foreground"]
            )
        else:
            body = Text(line, style=_line_style(line, diff, default))
        if code:
            grid.add_row(
                prefix, Text(match.group(1) if match else "", style=muted), "", body
            )
        else:
            grid.add_row(prefix, SeparatorWrap(body))
    if shown == len(lines):
        return grid
    rest = len(lines) - shown
    more = (
        f"… {rest} more {'line' if rest == 1 else 'lines'}"
        if language == "en"
        else f"… ещё {i18n.count_noun(language, rest, ('строка', 'строки', 'строк'), ('line', 'lines'))}"
    )
    return Group(grid, Text(f"{' ' * len(_RESULT_PREFIX)}{more} · ctrl+o", style=muted))


def transcript_row(
    event: JsonObject, language: str = "ru", *, expanded: bool = False
) -> RenderableType:
    """One event of the «Сессия» tab as Claude CLI shows it: a message, a tool call or an outcome
    is a ● line; a tool result, stderr and a QA stage's result hang under it on └; a Codex log
    line continues the message text; a system note and an omitted stretch are muted."""
    kind, text = str(event.get("kind", "event")), str(event.get("text", ""))
    if kind in {"tool-result", "stderr", "stage-result"}:
        return _result(kind, text, language, expanded)
    if kind == "log":
        return Text(f"  {text}", style=brand.PALETTE["muted"])
    return _bullet(kind, text)


def event_row(event: JsonObject, language: str = "ru") -> Table:
    """One line of the «События» tab: the chip of the kind (the legend under the tab names it),
    then the first line of the text, cut with an ellipsis."""
    kind, text = str(event.get("kind", "event")), str(event.get("text", ""))
    glyph, _label, colour = _event_look(kind, text, language)
    row = Table.grid(padding=(0, 1), expand=True)
    row.add_column(width=CHIP_WIDTH, no_wrap=True)
    row.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
    lines = text.splitlines() or [""]
    more = len(lines) - 1
    shown = Text(lines[0], style=brand.PALETTE["foreground"])
    if more:
        shown.append(f"  +{more}", style=brand.PALETTE["muted"])
    row.add_row(_chip(glyph, colour), shown)
    return row


def legend_text(language: str = "ru") -> Columns:
    """The legend under the «События» tab: every chip with its kind, in columns that never split a
    chip from its word. The «Сессия» tab reads as Claude CLI and needs none."""
    items = []
    for kind in EVENT_KINDS:
        glyph, label, colour = _event_look(kind, "", language)
        item = Text()
        item.append_text(_chip(glyph, colour))
        item.append(f" {label}", style=brand.PALETTE["muted"])
        items.append(item)
    return Columns(items, padding=(0, 2))


# The longest label of `context_rows` in either language: «Dispatch», «Snapshot», «Worktree».
CONTEXT_LABEL_WIDTH = 8


def context_rows(
    snapshot: JsonObject, width: int, t: Callable[[str], str]
) -> list[tuple[str, Text]]:
    """The launch facts of the context panel: one short line each, coloured by meaning. `width` is
    the room for a value; a long identifier is cut with an ellipsis."""
    room = max(width, 12)
    role = str(snapshot.get("role") or "—")
    runtime = {"claude": "Claude Code", "codex": "Codex"}.get(
        str(snapshot.get("runtime") or ""), str(snapshot.get("runtime") or "—")
    )
    mode = str(snapshot.get("access_mode") or "inherit")
    failure = snapshot.get("failure")
    reason = (
        str(failure.get("error") or failure.get("kind") or "")
        if isinstance(failure, dict)
        else ""
    )
    rows: list[tuple[str, Text]] = []
    if reason:
        rows.append(("Причина", Text(reason, style=brand.PALETTE["error"])))
    rows.append(
        (
            "Dispatch",
            Text(
                brand.shorten(brand.short_dispatch(str(snapshot.get("dispatch_id") or "—")), room),
                style=brand.PALETTE["primary"],
            ),
        )
    )
    rows.append(
        ("Роль", Text(role, style=f"bold {brand.ROLE_COLORS.get(role, brand.PALETTE['foreground'])}"))
    )
    rows.append(("Runtime", Text(runtime, style=brand.PALETTE["foreground"])))
    rows.append(("Модель", Text(str(snapshot.get("model") or "—"), style=brand.PALETTE["foreground"])))
    rows.append(("Усилие", Text(str(snapshot.get("effort") or "—"), style=brand.PALETTE["muted"])))
    rows.append(
        (
            "Запуск",
            Text(mode, style=brand.PALETTE["primary" if mode == "container" else "muted"]),
        )
    )
    session = snapshot.get("runtime_session_id")
    rows.append(
        (
            "Сессия",
            Text(brand.shorten(str(session), room), style=brand.PALETTE["muted"])
            if session
            else Text(t("не наблюдалась"), style=brand.PALETTE["muted"]),
        )
    )
    commit = snapshot.get("snapshot_commit")
    rows.append(
        (
            "Snapshot",
            Text(str(commit)[:12], style=brand.PALETTE["foreground"])
            if commit
            else Text(t("не наблюдался"), style=brand.PALETTE["muted"]),
        )
    )
    rows.append(
        (
            "Worktree",
            Text(_worktree(str(snapshot.get("worktree") or "—"), room), style=brand.PALETTE["muted"]),
        )
    )
    return rows


def _worktree(path: str, room: int) -> str:
    """The worktree path when it fits, else `…/` and its directory, which is named after the
    branch; the table wraps a directory too long for one line at its separators."""
    return path if len(path) <= room else f"…/{Path(path).name}"


def context_table(rows: list[tuple[str, Text]], language: str) -> Table:
    """The context facts as a grid: the label column is as wide as its longest label."""
    labels = [i18n.fact_label(language, label) for label, _ in rows]
    table = Table.grid(padding=(0, 1), expand=True)
    table.add_column(width=CONTEXT_LABEL_WIDTH, no_wrap=True, style=brand.PALETTE["muted"])
    table.add_column(ratio=1, overflow="fold")
    for label, (_, value) in zip(labels, rows):
        table.add_row(label, SeparatorWrap(value))
    return table


def readiness_text(snapshot: JsonObject) -> Text:
    """The environment checks, one per line: ● confirmed, ■ refuted, ○ not checked."""
    model_report = snapshot.get("model_self_report") or {}
    tree = snapshot.get("worktree_attestation") or {}
    checks = Text()
    for index, (name, verified) in enumerate(
        (
            ("Checkout", tree.get("match") if isinstance(tree, dict) else None),
            ("Git metadata", None),
            ("Ledger / inbox", None),
            ("Self-report", model_report.get("match") if isinstance(model_report, dict) else None),
        )
    ):
        state = "ok" if verified is True else "fail" if verified is False else "skipped"
        if index:
            checks.append("\n")
        checks.append(f"{icons.STATUS_ICONS[state]} ", style=brand.STATUS_COLORS[state])
        checks.append(name, style=brand.PALETTE["foreground" if state != "skipped" else "muted"])
    return checks


def observe(repo: Path, dispatch: str, offset: int) -> JsonObject:
    from harness.orchestration.workflow.delivery import observe_dispatch

    return observe_dispatch(
        argparse.Namespace(
            repo=str(repo), state_dir=None, dispatch=dispatch, offset=offset
        )
    )


class WorkerDetails(Translated, ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Назад")]
    DEFAULT_CSS = """
    WorkerDetails { align: center middle; }
    WorkerDetails > Vertical { width: 90%; height: 80%; border: round $primary; padding: 1; background: $surface; }
    WorkerDetails VerticalScroll { height: 1fr; }
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical():
            with VerticalScroll():
                yield Static(self.text, markup=False, classes="no-i18n")
            yield Button("Назад", id="close-worker-details")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class NativePermissionDialog(Translated, ModalScreen[bool | None]):
    """One native operator response; cancelling leaves the request pending."""

    BINDINGS = [Binding("escape", "cancel", "Отмена")]
    DEFAULT_CSS = WorkerDetails.DEFAULT_CSS.replace(
        "WorkerDetails", "NativePermissionDialog"
    )

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Запрос разрешения native runtime", markup=False)
            with VerticalScroll():
                yield Static(self.text, markup=False, classes="no-i18n")
            with Horizontal(classes="actions"):
                yield Button("Отклонить", id="native-deny")
                yield Button("Разрешить один раз", id="native-allow", variant="primary")
                yield Button("Отмена", id="native-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(
            True
            if event.button.id == "native-allow"
            else False
            if event.button.id == "native-deny"
            else None
        )


class WorkerObservationScreen(ConsoleShell):
    """A passive view. Closing/reconnecting never starts or terminates a worker."""

    SECTION = "Agent activity"
    IS_SECTION_ROOT = True
    CRUMBS = "Главная › Ход работы"
    HAS_CONTEXT = True
    IDS = ShellIds(
        navigation="worker-navigation",
        menu="worker-sections",
        content="worker-content",
        breadcrumbs="worker-breadcrumbs",
        toggle="worker-menu",
        body="worker-columns",
        context="worker-context",
    )
    # Four panes (menu, sessions, stream, context) need more room than the shell's default: below
    # 140 columns the context folds into a collapsible block under the stream.
    CONTEXT_SIDE_MIN = 140
    CONTEXT_TITLE = "Контекст запуска"
    AUTO_FOCUS = "#worker-picker"
    BINDINGS = [
        Binding("r", "refresh", "Обновить"),
        Binding("ctrl+o", "toggle_results", "Весь вывод"),
        *(Binding(f"alt+{i+1}", f"select_session({i})", show=False) for i in range(3)),
    ]
    DEFAULT_CSS = brand.shell_css("""
    WorkerObservationScreen #worker-panes { height: 1fr; }
    WorkerObservationScreen.-spacious.-tight #worker-sessions { width: 26; }
    WorkerObservationScreen #worker-sessions { width: 34; height: 1fr; background: transparent; border-right: solid $border-subtle; padding: 0 1; }
    WorkerObservationScreen #worker-live { width: 2; height: 1; margin-left: 1; color: $success; }
    WorkerObservationScreen #worker-session-count { height: 1; padding: 0 1; color: $text-muted; }
    WorkerObservationScreen #worker-picker { height: 1fr; border: none; margin: 0; padding: 0; }
    WorkerObservationScreen #worker-picker > .option-list--option { padding: 0 1; }
    WorkerObservationScreen #worker-picker > .option-list--separator { color: $border-subtle; }
    WorkerObservationScreen #worker-main { width: 1fr; min-width: 0; height: 1fr; }
    WorkerObservationScreen #worker-heading { height: auto; min-height: 1; padding: 0 2; }
    WorkerObservationScreen #worker-title { width: 1fr; height: 1; text-style: bold; }
    WorkerObservationScreen #worker-badge { width: auto; color: $text-muted; }
    /* The strip above names the ticket, role and dispatch and the context names the runtime, so
       the wide layout leaves out the subtitle that repeats them. */
    WorkerObservationScreen #worker-subtitle { display: none; height: 1; padding: 0 2; color: $text-muted; }
    WorkerObservationScreen.-narrow #worker-subtitle { display: block; }
    WorkerObservationScreen #worker-pipeline { height: 1; padding: 0 2; }
    WorkerObservationScreen #worker-status { height: auto; max-height: 6; padding: 0 2; border-top: solid $border-subtle; border-bottom: solid $border-subtle; color: $text-muted; }
    WorkerObservationScreen #worker-tabs { height: 1fr; }
    WorkerObservationScreen TabPane { padding: 0; }
    WorkerObservationScreen ContentSwitcher { height: 1fr; }
    WorkerObservationScreen Tabs { padding: 0 2; }
    /* 100%, not the default 1fr: a vertical layout takes the filter's side margins off an fr width,
       so the events log stood 4 cells short of the pane and its scrollbar off the edge. */
    WorkerObservationScreen #worker-output, WorkerObservationScreen #worker-events { width: 100%; height: 1fr; border: none; margin: 0; padding: 0 2; }
    WorkerObservationScreen #worker-filter { width: 30; height: 1; margin: 0 2; }
    WorkerObservationScreen #worker-access-scroll, WorkerObservationScreen #worker-execution-scroll { height: 1fr; padding: 0 2; }
    WorkerObservationScreen #worker-timeline { height: 1fr; border: none; margin: 0; padding: 0 2; }
    WorkerObservationScreen #worker-access-facts { height: auto; }
    WorkerObservationScreen #worker-actions { height: 4; padding: 0 2; border-top: solid $component-border; overflow-x: auto; }
    WorkerObservationScreen #worker-permissions-note { height: auto; margin-top: 1; color: $text-muted; }
    WorkerObservationScreen .worker-legend { height: auto; padding: 0 2; border-top: solid $border-subtle; }
    WorkerObservationScreen #worker-actions Button { margin-right: 1; min-width: 5; }
    WorkerObservationScreen #worker-stop { color: $error; }
    WorkerObservationScreen #worker-cost { height: 1; padding: 0 2; color: $text-muted; }
    WorkerObservationScreen #worker-switch { display: none; }
    WorkerObservationScreen.-narrow #worker-switch { display: block; }
    WorkerObservationScreen.-narrow #worker-sessions { display: none; }
    WorkerObservationScreen.-narrow.-sessions-open #worker-sessions { display: block; }
    WorkerObservationScreen.-narrow #worker-pipeline { height: 1; }
    WorkerObservationScreen.-narrow #worker-heading { height: 1; min-height: 1; padding: 0 2; }
    WorkerObservationScreen.-narrow #worker-title { height: 1; }
    WorkerObservationScreen.-narrow #worker-cost { display: none; }
    WorkerObservationScreen.-narrow #worker-output, WorkerObservationScreen.-narrow #worker-events { padding: 0 2; }
    WorkerObservationScreen.-narrow #worker-badge { max-width: 30; }
    WorkerObservationScreen.-focus #worker-navigation, WorkerObservationScreen.-focus #worker-sessions, WorkerObservationScreen.-focus #worker-context { display: none; }
    """)
    # The shell's rules plus this screen's own, which must outrank the app's generic widget rules.
    CSS = SHELL_CSS + brand.shell_css("""
    .shell #worker-sessions { background: transparent; }
    /* The run context holds one short fact per line (a dispatch reads as d8e030c3f, the model
       apart from its effort), so it gives its room to the work. Here, not in DEFAULT_CSS: the
       shell's own width rules come in `CSS` and would win over a default rule. */
    .shell.-spacious #worker-context, .shell.-spacious.-roomy #worker-context { width: 32; }
    /* The context starts on the first row, and the access check sits right under the checks. */
    .shell #worker-context-title { margin-top: 0; }
    .shell #worker-readiness { margin-bottom: 0; }
    .shell #worker-permissions-note { margin-top: 0; }
    .shell #worker-picker, .shell #worker-picker:focus { border: none; background: transparent; }
    .shell #worker-picker > .option-list--option-highlighted, .shell #worker-picker:focus > .option-list--option-highlighted {
        background: $row-highlight; color: $foreground; text-style: none;
    }
    .shell #worker-actions Button { border: round $component-border; color: $foreground; }
    .shell #worker-actions Button:hover, .shell #worker-actions Button:focus { border: round $primary; color: $primary; }
    .shell #worker-actions #worker-stop { color: $error; }
    .shell.-wide #worker-actions, .shell.-spacious #worker-actions { height: 2; padding: 0 1; }
    .shell.-wide #worker-actions Button, .shell.-wide #worker-actions Button:hover, .shell.-wide #worker-actions Button:focus,
    .shell.-spacious #worker-actions Button, .shell.-spacious #worker-actions Button:hover, .shell.-spacious #worker-actions Button:focus { border: none; height: 1; min-width: 0; padding: 0; margin-right: 0; }
    .shell.-wide #worker-actions Button:focus, .shell.-spacious #worker-actions Button:focus { background: $selection-background; color: $selection-foreground; }
    """)

    def __init__(
        self, repo: Path, dispatch: str | None = None, *, observer: Observer = observe
    ) -> None:
        super().__init__()
        self.repo = repo
        self.dispatch = dispatch
        self.observer = observer
        self._stream_offset = 0
        self._observer_offset = 0
        self._steps_failure: str | None = None
        self.snapshot: JsonObject = {}
        self._events: list[JsonObject] = []
        # ctrl+o shows every line of the tool results on the «Сессия» tab.
        self._expanded = False
        self._last_operation = "—"
        self._polls = PollGate()
        # Bumped when the view starts over, so a late poll of the previous view is dropped.
        self._generation = 0
        # The ledger is read off the UI thread after mount; until then only the requested
        # dispatch is listed and already observed.
        found = session_choices(reports.LedgerView(), dispatch)
        self._stages, self._batches, self._choices = (
            found.stages,
            found.batches,
            found.choices,
        )
        self._timer: Timer | None = None
        # What the runtime observes of the execution and the batch's orchestration timeline,
        # each read at its own cadence (#1296).
        self._execution: ExecutionSummary | None = None
        self._execution_asked = float("-inf")
        self._timeline: reports.BatchTimeline | None = None
        self._timeline_asked = float("-inf")

    def _session_card(self, label: str, dispatch_id: str) -> Text:
        stage = self._stages.get(dispatch_id)
        language = getattr(self.app, "language", "ru")
        if stage is None:
            card = Text(
                wrap_value(label, 18) + "\n\n", style=brand.PALETTE["foreground"]
            )
            return card.append_text(status_caption(session_status("unknown"), language))
        # The text room of an option: the list less the scrollbar it gets once the cards fill it
        # (the cards are drawn before it shows) and the option's side padding.
        picker = self.query_one("#worker-picker", OptionList)
        room = picker.content_size.width - picker.styles.scrollbar_size_vertical - 2
        outcome = stage.report.outcome if stage.report is not None else ""
        caption = status_caption(session_status(stage.state, outcome), language).plain
        return session_card(
            ticket=stage.ticket,
            role=stage.role,
            dispatch_id=dispatch_id,
            state=stage.state,
            language=language,
            # The dispatch ID fits one line of the list, however wide the list is.
            id_limit=max(12, room),
            # A short dispatch and its caption share a line when the list has room: two lines a card.
            stacked=cell_len(f"{brand.short_dispatch(dispatch_id)} · {caption}") > room,
            outcome=outcome,
        )

    def _paint_sessions(self) -> None:
        """The session count and cards in the current language, with the observed one highlighted."""
        language = getattr(self.app, "language", "ru")
        self.query_one("#worker-session-count", Static).update(
            i18n.tr_text(language, f"РАБОЧИЕ СЕССИИ   {len(self._choices)}")
        )
        picker = self.query_one("#worker-picker", OptionList)
        picker.set_options(session_options(self._choices, self._session_card))
        if self.dispatch is not None:
            picker.highlighted = picker.get_option_index(self.dispatch)

    def _load_sessions(self) -> None:
        repo, dispatch = self.repo, self.dispatch

        def load() -> None:
            found = session_choices(reports.load_ledger_view(repo), dispatch)
            call_from_worker(self, lambda: self._show_sessions(found))

        self.run_worker(load, thread=True, group="sessions", exit_on_error=False)

    def _show_sessions(self, found: Sessions) -> None:
        self._stages, self._batches, self._choices = (
            found.stages,
            found.batches,
            found.choices,
        )
        if self.dispatch is None and self._choices:
            self._restart(self._choices[0][1])
        elif self.dispatch is None:
            # Nothing to choose: say why instead of asking for a choice.
            language = getattr(self.app, "language", "ru")
            self.query_one("#worker-subtitle", Static).update(
                i18n.tr(language, "Рабочих сессий нет: ledger не записал ни одного dispatch")
            )
            self.query_one("#worker-status", Static).update(
                icons.tr(language, "○ Наблюдать нечего. Сессия появится, когда координатор запустит worker.")
            )
        self._paint_sessions()

    def compose_strip(self) -> ComposeResult:
        yield Button("Сессии", id="worker-switch", compact=True)
        yield WrappedValue("Выбранный batch / dispatch", id="worker-selection")
        yield Button("История batch →", id="worker-recovery", compact=True)

    def compose_content(self) -> ComposeResult:
        with Horizontal(id="worker-panes"):
            with Vertical(id="worker-sessions"):
                yield Static(
                    f"РАБОЧИЕ СЕССИИ   {len(self._choices)}",
                    id="worker-session-count",
                    classes="no-i18n",
                )
                yield OptionList(id="worker-picker")
            with Vertical(id="worker-main"):
                with Horizontal(id="worker-heading"):
                    yield Static(
                        "Наблюдение за работой",
                        id="worker-title",
                        classes="no-i18n",
                        markup=False,
                    )
                    yield Static(
                        "○ Ожидание",
                        id="worker-badge",
                        classes="no-i18n",
                        markup=False,
                    )
                    yield LiveDot(id="worker-live")
                yield Static(
                    "Выберите рабочую сессию",
                    id="worker-subtitle",
                    markup=False,
                    classes="no-i18n",
                )
                yield Static(
                    "architect  →  developer  →  review  →  QA  →  publish",
                    id="worker-pipeline",
                    classes="no-i18n",
                )
                yield Static(
                    "○ Ожидание наблюдения",
                    id="worker-status",
                    markup=False,
                    classes="no-i18n",
                )
                with TabbedContent(id="worker-tabs"):
                    with TabPane("Сессия", id="session"):
                        yield RichLog(
                            id="worker-output",
                            max_lines=500,
                            min_width=1,
                            wrap=True,
                            markup=False,
                            highlight=False,
                        )
                    with TabPane("События", id="events"):
                        yield Select(
                            [
                                ("Все события", "all"),
                                ("Вывод", "output"),
                                ("Инструменты", "tool"),
                                ("Ошибки", "error"),
                                ("Разрешения", "permission"),
                            ],
                            value="all",
                            allow_blank=False,
                            id="worker-filter",
                            compact=True,
                        )
                        yield RichLog(
                            id="worker-events",
                            max_lines=500,
                            min_width=1,
                            wrap=True,
                            markup=False,
                            highlight=False,
                        )
                        yield Static(legend_text(), classes="worker-legend no-i18n")
                    with TabPane("Хронология batch", id="orchestration"):
                        yield RichLog(
                            id="worker-timeline",
                            max_lines=TIMELINE_LIMIT * 2,
                            min_width=1,
                            wrap=True,
                            markup=False,
                            highlight=False,
                        )
                    with TabPane("Выполнение", id="execution"):
                        with VerticalScroll(id="worker-execution-scroll"):
                            yield WrappedValue(
                                "Runtime ещё не опрошен",
                                id="worker-execution-facts",
                            )
                    with TabPane("Доступы", id="access"):
                        with VerticalScroll(id="worker-access-scroll"):
                            yield WrappedValue(
                                "Данные проверки ещё не получены",
                                id="worker-access-facts",
                            )
                            yield Button(
                                "Запрос native",
                                id="worker-permission-inline",
                                disabled=True,
                            )
                with Horizontal(id="worker-actions"):
                    yield Button("Развернуть сессию", id="worker-focus")
                    yield Button("Детали", id="worker-details")
                    stop = Button(f"{icons.STOP} Остановить", id="worker-stop", disabled=True)
                    stop.tooltip = "Этот адаптер не предоставляет подтверждённый канал остановки. Закрытие панели не останавливает worker."
                    yield stop
                    yield Button(icons.REFRESH, id="worker-reconnect")
                yield Static(
                    "Наблюдение · без дополнительных LLM-вызовов",
                    id="worker-cost",
                )

    def compose_context(self) -> ComposeResult:
        yield Static(
            f"{icons.LAUNCH_CONTEXT} КОНТЕКСТ ЗАПУСКА", id="worker-context-title", classes="context-label"
        )
        yield Button(
            "Запрос native",
            id="worker-permission",
            disabled=True,
            compact=True,
        )
        yield Static(
            "Ожидание данных сессии", id="worker-context-facts", classes="context-value"
        )
        yield Static("ГОТОВНОСТЬ СРЕДЫ", classes="context-label")
        yield Static(
            "○ Не проверено",
            id="worker-readiness",
            classes="context-value no-i18n",
            markup=False,
        )
        yield Button("Проверка доступов →", id="worker-access", compact=True)
        yield Static(
            "Разрешения и hooks действуют; монитор их не выдаёт.",
            id="worker-permissions-note",
        )

    def on_resize(self, event: events.Resize) -> None:
        super().on_resize(event)
        # From 140 to 159 columns three panes share the screen; a narrower session list leaves the
        # main pane room for its one-line action bar.
        tight = event.size.width < TIGHT_WIDTH
        if tight != self.has_class("-tight"):
            self.set_class(tight, "-tight")
            # The session cards cut their dispatch IDs to the list's new width.
            self.call_after_refresh(self._paint_sessions)

    def on_mount(self) -> None:
        self._timer = self.set_interval(1, self.action_refresh)
        self.action_refresh()
        self._load_sessions()
        self.translate_now()

    def on_unmount(self) -> None:
        if self._timer:
            self._timer.stop()
        # Only local observation jobs are cancelled by Textual. The external runtime is never
        # owned by this screen and keeps running when the screen closes.

    def action_refresh(self) -> None:
        dispatch = self.dispatch
        if not dispatch:
            return
        generation = self._generation
        if not self._polls.begin(generation):
            if self._polls.stalled(generation):
                self._show_unavailable()
            return
        observer_offset, server_offset = self._observer_offset, self._stream_offset
        steps_failure = self._steps_failure
        reader: StepsReader | None = getattr(
            getattr(self.app, "home_client", None), "worker_steps", None
        )
        now = time.monotonic()
        ask_execution = now - self._execution_asked >= EXECUTION_SECONDS
        batch_id = self.snapshot.get("batch_id")
        ask_timeline = (
            isinstance(batch_id, str)
            and bool(batch_id)
            and now - self._timeline_asked >= TIMELINE_SECONDS
        )
        if ask_execution:
            self._execution_asked = now
        if ask_timeline:
            self._timeline_asked = now
        repo = self.repo

        def poll() -> None:
            result = poll_worker(
                repo,
                dispatch,
                self.observer,
                reader,
                observer_offset=observer_offset,
                server_offset=server_offset,
                steps_failure=steps_failure,
            )
            call_from_worker(self, lambda: self._polled(result, generation))
            if ask_execution:
                execution = observe_execution(repo, dispatch)
                call_from_worker(self, lambda: self._executed(execution, generation))
            if ask_timeline:
                try:
                    timeline = reports.load_ledger_view(repo).timeline(str(batch_id))
                except Exception:
                    timeline = None  # The ledger cannot be read now: keep the last timeline.
                if timeline is not None:
                    call_from_worker(self, lambda: self._timelined(timeline, generation))

        self.run_worker(poll, thread=True, group="observation", exit_on_error=False)

    def _polled(self, result: Poll, generation: int) -> None:
        self._polls.finish(generation)
        if generation != self._generation or not self.dispatch:
            return
        self._observer_offset = result.observer_offset
        self._steps_failure = result.steps_failure
        if result.snapshot.get("steps_source") != "observer":
            self._stream_offset = result.snapshot.get(
                "next_offset", self._stream_offset
            )
        self._render_snapshot(result.snapshot, self.dispatch)

    def _executed(self, summary: ExecutionSummary | None, generation: int) -> None:
        if generation != self._generation or not self.dispatch:
            return
        self._execution = summary
        self._paint_execution()

    def _paint_execution(self) -> None:
        language = getattr(self.app, "language", "ru")
        lines = execution_lines(self._execution, lambda text: i18n.tr_text(language, text))
        self.query_one("#worker-execution-facts", WrappedValue).set_value("\n".join(lines))

    def _timelined(self, timeline: reports.BatchTimeline, generation: int) -> None:
        if generation != self._generation or not self.dispatch:
            return
        if self._timeline is not None and self._timeline.events == timeline.events:
            return
        self._timeline = timeline
        log = self.query_one("#worker-timeline", RichLog)
        log.clear()
        rows = timeline_rows(timeline)
        if rows:
            log.write(timeline_table(rows), expand=True)
            log.write(
                Group(Text(""), timeline_legend(rows, getattr(self.app, "language", "ru"))),
                expand=True,
            )

    def _show_unavailable(self) -> None:
        self.query_one("#worker-status", Static).update(
            icons.tr_text(
                getattr(self.app, "language", "ru"),
                f"{icons.STATUS_ICONS['warn']} Наблюдение недоступно; исход процесса неизвестен. Повторный worker не запускается.",
            )
        )

    def _render_snapshot(self, snapshot: JsonObject, dispatch: str) -> None:
        if dispatch != self.dispatch:
            return
        language = getattr(self.app, "language", "ru")

        def t(text: str) -> str:
            return icons.tr_text(language, text)

        if snapshot.get("observation_error"):
            self._show_unavailable()
            return
        self.snapshot = snapshot
        for button_id in ("worker-permission", "worker-permission-inline"):
            self.query_one(f"#{button_id}", Button).disabled = not bool(
                snapshot.get("permission_requests")
            )
        self.query_one("#worker-permission", Button).display = bool(
            snapshot.get("permission_requests")
        )
        startup = snapshot.get("startup", {})
        observation = startup.get("observation")
        worker = (
            observation.get("state", "unknown")
            if isinstance(observation, dict)
            else startup.get("worker_state", "unknown")
        )
        if worker in {"reported", "rejected-at-startup"}:
            worker = "unknown"  # Lifecycle evidence does not prove process termination.
        staged = snapshot.get("report_staged") and not snapshot.get("report_recorded")
        for event in snapshot.get("events", []):
            if event.get("kind") in {"tool", "output", "permission", "error"}:
                self._last_operation = str(event.get("text") or "—").splitlines()[0][
                    :100
                ]
        process = process_line(snapshot, worker, language)
        heartbeat = heartbeat_line(snapshot, language)
        lines = [
            f"{snapshot.get('batch_id')} / {brand.short_dispatch(str(dispatch))} · {snapshot.get('role')}",
            process.plain,
            heartbeat.plain,
            f"{t('Операция')}: {self._last_operation}",
        ]
        exit_evidence = snapshot.get("runtime_exit")
        if isinstance(exit_evidence, dict):
            lines.append(
                f"exit: {exit_evidence['exit_code']} · {snapshot.get('access_mode', 'inherit')}"
            )
        warn = icons.STATUS_ICONS["warn"]
        if snapshot.get("permission_requests"):
            lines.append(
                t(f"{warn} Требуется разрешение native runtime; решение принимает человек.")
            )
        failure = snapshot.get("failure")
        if isinstance(failure, dict):
            lines.append(
                f"{warn} "
                + str(
                    failure.get("error") or failure.get("kind") or "refused"
                ).splitlines()[0][:140]
            )
        if staged:
            lines.append(
                t(
                    f"{warn} Отчёт ожидает доставки; завершение процесса не означает приёмку работы."
                )
            )
        if startup.get("deadline_exceeded"):
            lines.append(
                t(f"{warn} Истёк срок первого self-report; таймаут не доказывает остановку.")
            )
        if snapshot.get("stream_state") in {"unavailable", "waiting"}:
            lines.append(t("○ Нет новых событий; это не проверка здоровья worker."))
        if snapshot.get("steps_source") == "plain":
            lines.append(
                t(f"{icons.PLAIN_LOG} Структура недоступна: показан хвост обычного лога worker.")
            )
        reason = snapshot.get("steps_reason")
        if isinstance(reason, str) and reason in STEP_REASONS:
            lines.append(
                f"{t(f'{warn} Шаги worker недоступны')}: {t(STEP_REASONS[reason])}. "
                + t("Исход worker от наблюдения не зависит.")
            )
        self._paint_context(snapshot, worker, lines)
        status = Text()
        status.append_text(process)
        status.append("\n")
        status.append_text(heartbeat)
        for line in lines[4:]:
            status.append("\n" + line, style=_status_colour(line))
        self.query_one("#worker-status", Static).update(status)
        output = self.query_one("#worker-output", RichLog)
        if snapshot.get("reset"):
            output.write(
                Text(
                    t(
                        f"{warn} Поток был сокращён или перезаписан; показана доступная история."
                    )
                )
            )
        # New events are appended; both logs are rebuilt only when the filter changes.
        events_log = self.query_one("#worker-events", RichLog)
        language = getattr(self.app, "language", "ru")
        for event in snapshot.get("events", []):
            self._events.append(event)
            if self._event_visible(event):
                output.write(
                    transcript_row(event, language, expanded=self._expanded),
                    expand=True,
                )
                events_log.write(event_row(event, language), expand=True)
        self._events = self._events[-500:]
        bar = self.query_one(TopBar)
        bar.crumbs = f"Главная › Оркестрация › {snapshot.get('batch_id')} › Сессии"
        bar.refresh_status()

    def _worker_crumbs(self, snapshot: JsonObject) -> list[Crumb]:
        """The path with the observed batch, which links to that batch's timeline when there is one."""
        batch = str(snapshot.get("batch_id") or "—")
        return [
            Crumb("Главная", section=HOME_SECTION),
            Crumb("Оркестрация", section="Orchestration"),
            Crumb(
                brand.shorten(batch, 23),
                action="open_batch" if batch in self._batches else None,
            ),
            Crumb("Ход работы"),
        ]

    def action_open_batch(self) -> None:
        from .reports import BatchTimelineScreen

        repo, batch_id = self.repo, self.snapshot.get("batch_id", "")

        def work() -> None:
            timeline = reports.load_ledger_view(repo).timeline(batch_id)

            def show() -> None:
                if timeline and self.is_mounted:
                    self.app.push_screen(BatchTimelineScreen(timeline, repo))

            call_from_worker(self, show)

        # The ledger is read off the UI thread, like the other screens do.
        self.run_worker(work, thread=True, group="open-batch", exclusive=True)

    def _paint_context(
        self, snapshot: JsonObject, worker: str, lines: list[str]
    ) -> None:
        language = getattr(self.app, "language", "ru")

        def t(value: str) -> str:
            return i18n.tr_text(language, value)

        ticket, role = snapshot.get("ticket") or "—", snapshot.get("role") or "—"
        status = session_status(snapshot.get("state", "unknown"))
        if snapshot.get("permission_requests"):
            status = PERMISSION_PENDING
        elif snapshot.get("state") in {"working", "dispatched"} and worker != "live":
            status = process_status(worker)
        self.query_one("#worker-title", Static).update(
            f"{ticket} · {t('Наблюдение за работой')}"
        )
        self.query_one("#worker-badge", Static).update(
            Text(icons.render_status(status, language), style=status.color)
        )
        runtime = {"claude": "Claude Code", "codex": "Codex"}.get(
            str(snapshot.get("runtime") or ""),
            str(snapshot.get("runtime") or "runtime —"),
        )
        self.query_one("#worker-subtitle", Static).update(
            f"{role} / {runtime} / {brand.shorten(brand.short_dispatch(str(snapshot.get('dispatch_id') or '')), 18)}"
        )
        pipeline = Text()
        for i, stage in enumerate(
            ("architect", "developer", "review", "QA", "publish")
        ):
            if i:
                pipeline.append(" → ", style=brand.PALETTE["muted"])
            active = stage == {"code-review": "review", "qa": "QA"}.get(role, role)
            pipeline.append(
                f" {stage} ",
                style=f"{brand.PALETTE['primary']} on {brand.SHELL_TOKENS['event-active-background']}"
                if active
                else brand.PALETTE["muted"],
            )
        self.query_one("#worker-pipeline", Static).update(pipeline)
        self.query_one(Breadcrumbs).set_crumbs(self._worker_crumbs(snapshot))
        self.query_one("#worker-selection", WrappedValue).set_value(
            f"{ticket} · {role} · {brand.short_dispatch(str(snapshot.get('dispatch_id') or ''))}"
        )
        facts = self.query_one("#worker-context-facts", Static)
        rows = context_rows(snapshot, facts.content_size.width - CONTEXT_LABEL_WIDTH - 1, t)
        facts.update(context_table(rows, language))
        readiness = readiness_text(snapshot)
        self.query_one("#worker-readiness", Static).update(readiness)
        self.query_one("#worker-access-facts", WrappedValue).set_value(
            "\n".join(f"{t(label)}: {value.plain}" for label, value in rows)
            + "\n\n"
            + readiness.plain
            + "\n\n"
            + "\n".join(lines)
        )

    def sync_language(self) -> None:
        language = getattr(self.app, "language", "ru")
        select = self.query_one("#worker-filter", Select)
        selected = select.value
        select.set_options(
            (i18n.tr(language, label), value)
            for label, value in [
                ("Все события", "all"),
                ("Вывод", "output"),
                ("Инструменты", "tool"),
                ("Ошибки", "error"),
                ("Разрешения", "permission"),
            ]
        )
        select.value = selected
        for legend in self.query(".worker-legend").results(Static):
            legend.update(legend_text(language))
        self._paint_sessions()
        if self.snapshot:
            self._render_snapshot({**self.snapshot, "events": []}, self.dispatch or "")
        super().sync_language()

    def _event_visible(self, event: JsonObject) -> bool:
        selected = self.query_one("#worker-filter", Select).value
        return selected == "all" or str(event.get("kind", "")).startswith(str(selected))

    def _rebuild_logs(self) -> None:
        """Write the kept events again: the filter or the fold of tool results changed."""
        output = self.query_one("#worker-output", RichLog)
        output.clear()
        events = self.query_one("#worker-events", RichLog)
        events.clear()
        language = getattr(self.app, "language", "ru")
        for row in self._events:
            if self._event_visible(row):
                output.write(
                    transcript_row(row, language, expanded=self._expanded), expand=True
                )
                events.write(event_row(row, language), expand=True)

    def action_toggle_results(self) -> None:
        """Show every line of the tool results on the «Сессия» tab, or fold them again."""
        self._expanded = not self._expanded
        self._rebuild_logs()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "worker-filter":
            self._rebuild_logs()
            return

    def _select_dispatch(self, dispatch: str) -> None:
        if dispatch != self.dispatch:
            self._restart(dispatch)

    def _restart(self, dispatch: str) -> None:
        """Observe `dispatch` from the start, asking the console server for its steps again."""
        self._generation += 1
        self.dispatch = dispatch
        self._stream_offset = 0
        self._observer_offset = 0
        self._steps_failure = None
        self.snapshot = {}
        self._events = []
        self._last_operation = "—"
        self._execution, self._execution_asked = None, float("-inf")
        self._timeline, self._timeline_asked = None, float("-inf")
        self.query_one("#worker-output", RichLog).clear()
        self.query_one("#worker-events", RichLog).clear()
        self.query_one("#worker-timeline", RichLog).clear()
        self.action_refresh()

    def action_select_session(self, index: int) -> None:
        if index < len(self._choices):
            self.query_one("#worker-picker", OptionList).highlighted = index
            self._select_dispatch(self._choices[index][1])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "worker-picker" and event.option.id:
            self._select_dispatch(event.option.id)

    async def action_section(self, index: int) -> None:
        # This screen is a view inside Orchestration: its menu entry still opens that section.
        await self.open_section(index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "worker-focus":
            self.toggle_class("-focus")
            event.button.label = i18n.tr(
                getattr(self.app, "language", "ru"),
                "Свернуть сессию" if self.has_class("-focus") else "Развернуть сессию",
            )
        elif event.button.id == "worker-switch":
            self.remove_class("-menu-open")
            self.toggle_class("-sessions-open")
            if self.has_class("-sessions-open"):
                self.call_after_refresh(
                    self.query_one("#worker-picker", OptionList).focus
                )
        elif event.button.id == "worker-access":
            self.query_one("#worker-tabs", TabbedContent).active = "access"
        elif event.button.id == "worker-reconnect":
            if self.dispatch:
                self._restart(self.dispatch)
        elif event.button.id == "worker-menu":
            self.remove_class("-sessions-open")  # the shell toggles the menu itself
        elif event.button.id in {"worker-permission", "worker-permission-inline"}:
            requests = self.snapshot.get("permission_requests", [])
            if not requests or not self.dispatch:
                return
            pending = requests[0]
            dispatch_id = self.dispatch
            description = f"{self.snapshot.get('batch_id')} / {brand.short_dispatch(str(dispatch_id))}\n{self.snapshot.get('worktree')}\nRequest: {pending['request_id']}\nTool: {pending['tool_name']}\n{pending['input_preview']}"

            def answered(allow: bool | None) -> None:
                if allow is None:
                    return

                def send_response() -> None:
                    from harness.orchestration.workflow.delivery import (
                        respond_native_permission,
                    )
                    from harness.orchestration.core.utils import CoordinatorError

                    try:
                        respond_native_permission(
                            self.repo,
                            dispatch_id,
                            pending["request_id"],
                            pending["request_sha256"],
                            allow=allow,
                        )
                    except CoordinatorError as exc:
                        message = exc.message
                        call_from_worker(
                            self, lambda: self.notify(message, severity="error")
                        )
                    call_from_worker(self, self.action_refresh)

                self.run_worker(
                    send_response,
                    thread=True,
                    group="native-permission",
                    exit_on_error=False,
                )

            self.app.push_screen(NativePermissionDialog(description), answered)
        elif event.button.id == "worker-details":
            lines = [
                f"{key}: {self.snapshot.get(key)}"
                for key in (
                    "batch_id",
                    "dispatch_id",
                    "role",
                    "worktree",
                    "model",
                    "runtime",
                    "effort",
                    "snapshot_commit",
                    "worktree_attestation",
                    "access_mode",
                    "runtime_exit",
                    "failure",
                    "launch_id",
                    "runtime_session_id",
                    "heartbeat_at",
                    "log_path",
                    "report_staged",
                    "report_recorded",
                )
            ]
            lines.append(
                "Stop/permissions: use the native runtime; observation grants no permissions."
            )
            self.app.push_screen(WorkerDetails("\n".join(lines)))
        elif event.button.id == "worker-recovery":
            self.action_open_batch()
        elif event.button.id == "worker-back":
            self.app.pop_screen()

    def launch(self, argv: list[str], runner: CommandRunner) -> None:
        """The already-confirmed send runs once, with its visible monitor mounted first."""

        def send() -> None:
            env = {**os.environ, "HARNESS_CONSOLE_ATTACHED": "1"}
            try:
                result = runner(argv, env=env, cwd=self.repo)
                if result.returncode:
                    from harness.orchestration.worker_observation import redact_visible

                    text = redact_visible(
                        result.stderr
                        or result.stdout
                        or "Runtime handoff failed; inspect dispatch status and native permissions."
                    )
                    call_from_worker(
                        self,
                        lambda: self.query_one("#worker-output", RichLog).write(
                            Text(text)
                        ),
                    )
            except OSError:
                call_from_worker(
                    self,
                    lambda: self.query_one("#worker-output", RichLog).write(
                        Text("Runtime handoff could not start.")
                    ),
                )
            call_from_worker(self, self.action_refresh)

        self.run_worker(send, thread=True, group="send", exit_on_error=False)
