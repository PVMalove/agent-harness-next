"""Icon vocabulary of the TUI, keeping `kernel/` and the Web UI untouched.

Every status and entity icon in `harness/console/tui/` comes from here, so the TUI reads in one
symbol style while `kernel/` (`brand.STATUS_ICONS`, `status.KINDS`, `i18n_strings`) and the Web UI
keep their shared contract unchanged. The icons are one geometric family: a filled shape is a state
reached, a hollow one a state not reached yet, and colour only adds to the shape.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from rich.text import Text

from ..kernel import brand, i18n
from ..kernel.status import Status

# One geometric family that the usual terminal fonts all draw themselves (DejaVu Sans Mono,
# Liberation Mono and Courier New, Consolas and Menlo carry these WGL4 shapes), so the icons share
# one size and one baseline. A glyph missing from the terminal font comes from a fallback font of
# another size, and the VS Code terminal squeezes one wider than its cell: that is why emoji and
# dingbats read as icons of different sizes. Each glyph is one cell (`rich.cells.cell_len == 1`).
# `↻` is the one exception: only an icon button shows it.
GLYPHS = frozenset("●○■□▲►◐◊♦×◌◦▪▫›⌂≡↔•☺↻")

# Health / check statuses (parallels `brand.STATUS_ICONS`).
STATUS_ICONS: dict[str, str] = {
    "ok": "●",
    "warn": "▲",
    "fail": "■",
    "skipped": "○",
}

# Session, ledger and process status kinds (parallels `status.KINDS`).
STATUS_KIND_ICONS: dict[str, str] = {
    "accepted": "●",
    "running": "►",
    "paused": "◐",
    "not_started": "○",
    "error": "■",
    "warning": "▲",
}

# Action, navigation and section icons used across TUI screens.
STOP = "□"
REFRESH = "↻"
BRANCH = "◦"
STAR = "◊"
LAUNCH_CONTEXT = "♦"
DELETE = "×"
PLAIN_LOG = "◌"
UNKNOWN = "▫"

# The one "in progress" icon of every loading or running line: the running status kind's icon.
LOADING = STATUS_KIND_ICONS["running"]


def loading(text: str) -> str:
    """`text` of a loading or running line, after the one "in progress" icon."""
    return f"{LOADING} {text}"


# Live source pulse.
LIVE_ON = "●"
LIVE_OFF = "○"

# Context group icons on the Home screen.
CONTEXT_ICONS: dict[str, str] = {
    "card-project": "⌂",
    "card-harness": "≡",
    "card-orchestration": "►",
    "card-repo-map": "↔",
    "card-memory": "◊",
}
CONTEXT_FALLBACK = "›"

# A worker role as one icon in its `brand.ROLE_COLORS` colour (the batch timeline's role column).
ROLE_ICONS: dict[str, str] = {
    "architect": "▲",
    "developer": "■",
    "code-review": "◊",
    "review": "◊",
    "qa": "●",
    "publish": "►",
    "verification": "♦",
    "coordinator": "≡",
    "human": "☺",
}
ROLE_FALLBACK = "•"

# A batch timeline event kind as one icon, its Russian and English word and its colour: a state
# change, a dispatch sent, a report returned, a decision (the flowchart diamond) and a risk.
TIMELINE_KINDS: dict[str, tuple[str, str, str, str]] = {
    "state": ("◐", "состояние", "state", brand.ROLE_COLORS["verification"]),
    "dispatch": ("►", "dispatch", "dispatch", brand.PALETTE["primary"]),
    "report": ("●", "отчёт", "report", brand.PALETTE["success"]),
    "decision": ("◊", "решение", "decision", brand.PALETTE["warning"]),
    "risk": ("▲", "риск", "risk", brand.PALETTE["error"]),
}


def timeline_icon(kind: str) -> tuple[str, str]:
    """A timeline event `kind` as its icon and colour; an unknown kind is the muted fallback."""
    glyph, _ru, _en, colour = TIMELINE_KINDS.get(kind, (ROLE_FALLBACK, "", "", brand.PALETTE["muted"]))
    return glyph, colour


def kinds_legend(kinds: Iterable[str], language: str = "ru") -> Text:
    """The timeline event `kinds`, each once in the order given, as its icon and word."""
    legend = Text()
    for kind in dict.fromkeys(kinds):
        glyph, colour = timeline_icon(kind)
        _glyph, ru, en, _colour = TIMELINE_KINDS.get(kind, ("", kind, kind, ""))
        if legend:
            legend.append("   ")
        legend.append(glyph, style=f"bold {colour}")
        legend.append(f" {en if language == 'en' else ru}", style=brand.PALETTE["muted"])
    return legend


def role_icon(role: str) -> tuple[str, str]:
    """`role` as its icon and colour; a role outside the set is the muted fallback, no role is
    empty."""
    if not role or role == "-":
        return "", brand.PALETTE["muted"]
    colour = brand.ROLE_COLORS.get(
        "code-review" if role == "review" else role,
        brand.PALETTE["primary"] if role in ROLE_ICONS else brand.PALETTE["muted"],
    )
    return ROLE_ICONS.get(role, ROLE_FALLBACK), colour


# Kernel glyphs and the TUI icons they read as. `○`, `◌` and `□` are the same in both.
_TO_TUI: tuple[tuple[str, str], ...] = (
    ("✔", "●"),
    ("✓", "●"),
    ("⚠️", "▲"),
    ("⚠", "▲"),
    ("✖", "■"),
    ("▶️", "►"),
    ("▶", "►"),
    ("⏸️", "◐"),
    ("Ⅱ", "◐"),
    ("🗑️", DELETE),
    ("⊘", DELETE),
    ("◉", LAUNCH_CONTEXT),
    ("⏹️", STOP),
    ("★", STAR),
)
_TO_KERNEL: tuple[tuple[str, str], ...] = (
    ("●", "✔"),
    ("▲", "⚠"),
    ("■", "✖"),
    ("►", "▶"),
    ("◐", "Ⅱ"),
    (DELETE, "⊘"),
    (LAUNCH_CONTEXT, "◉"),
    (STAR, "★"),
)
# Kernel glyphs that are already TUI icons: a line led by one is looked up without it too.
_SHARED = ("○", "◌", "□")


def status_symbol(status: Status) -> str:
    """The TUI icon for `status`."""
    return STATUS_KIND_ICONS.get(status.kind, restyle_text(status.symbol))


def render_status(status: Status, language: str) -> str:
    """`status` as its TUI icon plus its label in `language`."""
    return f"{status_symbol(status)} {status.text(language)}"


def restyle_text(text: str) -> str:
    """Rewrite kernel geometric status glyphs in `text` to TUI icons."""
    for old, new in _TO_TUI:
        if old in text:
            text = text.replace(old, new)
    return text


def to_kernel_glyphs(text: str) -> str:
    """Convert TUI icons back to kernel glyphs for `i18n_strings` lookup."""
    for icon, glyph in _TO_KERNEL:
        if icon in text:
            text = text.replace(icon, glyph)
    return text


def _icon_and_text(text: str) -> tuple[str, str]:
    """A leading kernel glyph and its space apart from the text after it; `("", text)` without."""
    for glyph in (*(glyph for _icon, glyph in _TO_KERNEL), *_SHARED):
        if text.startswith(glyph + " "):
            return glyph + " ", text[len(glyph) + 1 :]
    return "", text


def _translate(translate: Callable[[str, str], str], language: str, text: str) -> str:
    """`translate` of `text`; a line after a status icon is looked up without its icon, so a
    fixed string keeps its translation when a screen marks it (`► Загрузка…`)."""
    kernel = to_kernel_glyphs(text)
    found = translate(language, kernel)
    icon, rest = _icon_and_text(kernel)
    if found == kernel and icon:
        found = icon + translate(language, rest)
    return restyle_text(found)


def tr(language: str, text: str) -> str:
    """Translate a fixed TUI string via `kernel/i18n` and keep TUI icons."""
    return _translate(i18n.tr, language, text)


def tr_text(language: str, text: str) -> str:
    """Translate dynamic TUI text via `kernel/i18n` and keep TUI icons."""
    return _translate(i18n.tr_text, language, text)
