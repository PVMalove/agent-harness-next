"""Emoji icon vocabulary for the TUI, keeping `kernel/` and the Web UI untouched.

Every status and entity icon in `harness/console/tui/` comes from here so the TUI reads in one
consistent emoji style while `kernel/` (`brand.STATUS_ICONS`, `status.KINDS`, `i18n_strings`) and
the Web UI keep their shared contract unchanged.
"""

from __future__ import annotations

from collections.abc import Callable

from ..kernel import i18n
from ..kernel.status import Status

# Every icon below is a single-codepoint Emoji_Presentation=Yes (`East_Asian_Width=W`) glyph with
# `rich.cells.cell_len(glyph) == 2` and no Variation Selector-16 (`\ufe0f`). Text-default glyphs +
# `\ufe0f` (such as `⚠️`, `▶️`, `⚙️`) report width 2 in Rich while VTE/xterm terminals advance the
# cursor by 1 cell, shifting vertical borders left and swallowing the space after the icon.

# Health / check statuses (parallels `brand.STATUS_ICONS`).
STATUS_ICONS: dict[str, str] = {
    "ok": "✅",
    "warn": "🔶",
    "fail": "❌",
    "skipped": "⚪",
}

# Session, ledger and process status kinds (parallels `status.KINDS`).
STATUS_KIND_ICONS: dict[str, str] = {
    "accepted": "✅",
    "running": "⏩",
    "paused": "⏳",
    "not_started": "⚪",
    "error": "❌",
    "warning": "🔶",
}

# Action, navigation and section icons used across TUI screens.
STOP = "🛑"
REFRESH = "🔄"
BRANCH = "🌿"
STAR = "⭐"
LAUNCH_CONTEXT = "🎯"
DELETE = "⛔"
PLAIN_LOG = "📄"
UNKNOWN = "❓"

# The one "in progress" icon of every loading or running line: the running status kind's icon.
LOADING = STATUS_KIND_ICONS["running"]


def loading(text: str) -> str:
    """`text` of a loading or running line, after the one "in progress" icon."""
    return f"{LOADING} {text}"


# Live source pulse (2 cells wide, matching `#worker-live { width: 2 }`).
LIVE_ON = "🟢"
LIVE_OFF = "⚪"

# Context group icons on the Home screen.
CONTEXT_ICONS: dict[str, str] = {
    "card-project": "🏠",
    "card-harness": "🧰",
    "card-orchestration": "🤖",
    "card-repo-map": "🧭",
    "card-memory": "🧠",
}
CONTEXT_FALLBACK = "📌"

_TO_TUI: tuple[tuple[str, str], ...] = (
    ("✔", "✅"),
    ("✓", "✅"),
    ("⚠️", "🔶"),
    ("⚠", "🔶"),
    ("✖", "❌"),
    ("○", "⚪"),
    ("◌", PLAIN_LOG),
    ("▶️", "⏩"),
    ("▶", "⏩"),
    ("⏸️", "⏳"),
    ("Ⅱ", "⏳"),
    ("🗑️", DELETE),
    ("⊘", DELETE),
    ("◉", LAUNCH_CONTEXT),
    ("⏹️", STOP),
    ("□", STOP),
    ("★", STAR),
)
_TO_KERNEL: tuple[tuple[str, str], ...] = (
    ("✅", "✔"),
    ("🔶", "⚠"),
    ("❌", "✖"),
    ("⚪", "○"),
    (PLAIN_LOG, "◌"),
    ("⏩", "▶"),
    ("⏳", "Ⅱ"),
    (DELETE, "⊘"),
    (LAUNCH_CONTEXT, "◉"),
    (STOP, "□"),
    (STAR, "★"),
)


def status_symbol(status: Status) -> str:
    """The TUI emoji icon for `status`."""
    return STATUS_KIND_ICONS.get(status.kind, restyle_text(status.symbol))


def render_status(status: Status, language: str) -> str:
    """`status` as its TUI emoji icon plus its label in `language`."""
    return f"{status_symbol(status)} {status.text(language)}"


def restyle_text(text: str) -> str:
    """Rewrite kernel geometric status glyphs in `text` to TUI emoji icons."""
    for old, new in _TO_TUI:
        if old in text:
            text = text.replace(old, new)
    return text


def to_kernel_glyphs(text: str) -> str:
    """Convert TUI emoji icons back to kernel glyphs for `i18n_strings` lookup."""
    for emoji, glyph in _TO_KERNEL:
        if emoji in text:
            text = text.replace(emoji, glyph)
    return text


def _icon_and_text(text: str) -> tuple[str, str]:
    """A leading kernel glyph and its space apart from the text after it; `("", text)` without."""
    for _emoji, glyph in _TO_KERNEL:
        if text.startswith(glyph + " "):
            return glyph + " ", text[len(glyph) + 1 :]
    return "", text


def _translate(translate: Callable[[str, str], str], language: str, text: str) -> str:
    """`translate` of `text`; a line after a status icon is looked up without its icon, so a
    fixed string keeps its translation when a screen marks it (`⏩ Загрузка…`)."""
    kernel = to_kernel_glyphs(text)
    found = translate(language, kernel)
    icon, rest = _icon_and_text(kernel)
    if found == kernel and icon:
        found = icon + translate(language, rest)
    return restyle_text(found)


def tr(language: str, text: str) -> str:
    """Translate a fixed TUI string via `kernel/i18n` and keep TUI emoji icons."""
    return _translate(i18n.tr, language, text)


def tr_text(language: str, text: str) -> str:
    """Translate dynamic TUI text via `kernel/i18n` and keep TUI emoji icons."""
    return _translate(i18n.tr_text, language, text)
