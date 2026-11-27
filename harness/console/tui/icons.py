"""Icon vocabulary of the TUI, keeping `kernel/` and the Web UI untouched.

Every status and entity icon in `harness/console/tui/` comes from here, so the TUI reads in one
symbol style while `kernel/` (`brand.STATUS_ICONS`, `status.KINDS`, `i18n_strings`) and the Web UI
keep their shared contract unchanged. The symbols are the owner's set (2026-11-27); colour tells
the kinds apart, the shape keeps them apart without colour.
"""

from __future__ import annotations

from collections.abc import Callable

from ..kernel import brand, i18n
from ..kernel.status import Status

# The owner's symbol set. Every icon below is one of these single-codepoint, one-cell glyphs
# (`rich.cells.cell_len(glyph) == 1`, no Variation Selector-16): a terminal advances the cursor by
# the width Rich counts, so borders and the space after an icon stay where they are.
GLYPHS = frozenset("※⁘⁖⁙⁕⁑›↬↫⌾∴∵◎◉☺✎✖✚✤✦⭓⭔⬢✣◈▿◃►")
# Glyphs of the set no icon uses: a terminal font rarely has them, the fallback glyph is wider than
# one cell, and the VS Code terminal squeezes it into the cell (`rescaleOverlappingGlyphs`), so a
# circle reads as a tall oval and a hexagon as a sliver. Dingbats are not squeezed.
SQUEEZED = frozenset("◎◉⬢⭓⭔⌾")

# Health / check statuses (parallels `brand.STATUS_ICONS`).
STATUS_ICONS: dict[str, str] = {
    "ok": "✦",
    "warn": "✤",
    "fail": "✖",
    "skipped": "⁘",
}

# Session, ledger and process status kinds (parallels `status.KINDS`).
STATUS_KIND_ICONS: dict[str, str] = {
    "accepted": "✦",
    "running": "►",
    "paused": "⁖",
    "not_started": "⁘",
    "error": "✖",
    "warning": "✤",
}

# Action, navigation and section icons used across TUI screens.
STOP = "◃"
REFRESH = "↫"
BRANCH = "↬"
STAR = "⁕"
LAUNCH_CONTEXT = "◈"
DELETE = "▿"
PLAIN_LOG = "∵"
UNKNOWN = "※"

# The one "in progress" icon of every loading or running line: the running status kind's icon.
LOADING = STATUS_KIND_ICONS["running"]


def loading(text: str) -> str:
    """`text` of a loading or running line, after the one "in progress" icon."""
    return f"{LOADING} {text}"


# Live source pulse.
LIVE_ON = "✦"
LIVE_OFF = "⁘"

# Context group icons on the Home screen.
CONTEXT_ICONS: dict[str, str] = {
    "card-project": "✎",
    "card-harness": "✣",
    "card-orchestration": "⁙",
    "card-repo-map": "↬",
    "card-memory": "∴",
}
CONTEXT_FALLBACK = "›"

# A worker role as one icon in its `brand.ROLE_COLORS` colour (the batch timeline's role column).
ROLE_ICONS: dict[str, str] = {
    "architect": "◈",
    "developer": "✎",
    "code-review": "∴",
    "review": "∴",
    "qa": "✚",
    "publish": "↬",
    "verification": "▿",
    "coordinator": "⁙",
    "human": "☺",
}
ROLE_FALLBACK = "›"


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


# Kernel glyphs and the TUI icons they read as. `✖` is the same in both.
_TO_TUI: tuple[tuple[str, str], ...] = (
    ("✔", "✦"),
    ("✓", "✦"),
    ("⚠️", "✤"),
    ("⚠", "✤"),
    ("○", "⁘"),
    ("◌", PLAIN_LOG),
    ("▶️", "►"),
    ("▶", "►"),
    ("⏸️", "⁖"),
    ("Ⅱ", "⁖"),
    ("🗑️", DELETE),
    ("⊘", DELETE),
    ("◉", LAUNCH_CONTEXT),
    ("⏹️", STOP),
    ("□", STOP),
    ("★", STAR),
)
_TO_KERNEL: tuple[tuple[str, str], ...] = (
    ("✦", "✔"),
    ("✤", "⚠"),
    ("⁘", "○"),
    (PLAIN_LOG, "◌"),
    ("►", "▶"),
    ("⁖", "Ⅱ"),
    (DELETE, "⊘"),
    (LAUNCH_CONTEXT, "◉"),
    (STOP, "□"),
    (STAR, "★"),
)
# A kernel glyph that is already a TUI icon: a line led by it is looked up without it too.
_SHARED = ("✖",)


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
