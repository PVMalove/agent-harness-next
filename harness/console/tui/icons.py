"""Emoji icon vocabulary for the TUI, keeping `kernel/` and the Web UI untouched.

Every status and entity icon in `harness/console/tui/` comes from here so the TUI reads in one
consistent emoji style while `kernel/` (`brand.STATUS_ICONS`, `status.KINDS`, `i18n_strings`) and
the Web UI keep their shared contract unchanged.
"""

from __future__ import annotations

import re

from ..kernel import i18n
from ..kernel.status import Status

# Health / check statuses (parallels `brand.STATUS_ICONS`).
STATUS_ICONS: dict[str, str] = {
    "ok": "✅",
    "warn": "⚠️",
    "fail": "❌",
    "skipped": "⚪",
}

# Session, ledger and process status kinds (parallels `status.KINDS`).
STATUS_KIND_ICONS: dict[str, str] = {
    "accepted": "✅",
    "running": "▶️",
    "paused": "⏸️",
    "not_started": "⚪",
    "error": "❌",
    "warning": "⚠️",
}

# Action, navigation and section icons used across TUI screens.
STOP = "⏹️"
REFRESH = "🔄"
BRANCH = "🌿"
STAR = "⭐"
LAUNCH_CONTEXT = "🎯"
DELETE = "🗑️"
PLAIN_LOG = "📄"
UNKNOWN = "❓"

# Live source pulse (2 cells wide, matching `#worker-live { width: 2 }`).
LIVE_ON = "🟢"
LIVE_OFF = "⚪"

# Context group icons on the Home screen.
CONTEXT_ICONS: dict[str, str] = {
    "card-project": "🏠",
    "card-harness": "⚙️",
    "card-orchestration": "🤖",
    "card-repo-map": "🗺️",
    "card-memory": "🧠",
}
CONTEXT_FALLBACK = "📌"

_TO_TUI: tuple[tuple[str, str], ...] = (
    ("✔", "✅"),
    ("✓", "✅"),
    ("✖", "❌"),
    ("○", "⚪"),
    ("◌", PLAIN_LOG),
    ("Ⅱ", "⏸️"),
    ("⊘", DELETE),
    ("◉", LAUNCH_CONTEXT),
    ("□", STOP),
    ("★", STAR),
)
_TO_KERNEL: tuple[tuple[str, str], ...] = (
    ("✅", "✔"),
    ("⚠️", "⚠"),
    ("❌", "✖"),
    ("⚪", "○"),
    (PLAIN_LOG, "◌"),
    ("▶️", "▶"),
    ("⏸️", "Ⅱ"),
    (DELETE, "⊘"),
    (LAUNCH_CONTEXT, "◉"),
    (STOP, "□"),
    (STAR, "★"),
)
_BARE_WARN = re.compile(r"⚠(?!\ufe0f)")
_BARE_PLAY = re.compile(r"▶(?!\ufe0f)")


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
    if "⚠" in text:
        text = _BARE_WARN.sub("⚠️", text)
    if "▶" in text:
        text = _BARE_PLAY.sub("▶️", text)
    return text


def to_kernel_glyphs(text: str) -> str:
    """Convert TUI emoji icons back to kernel glyphs for `i18n_strings` lookup."""
    for emoji, glyph in _TO_KERNEL:
        if emoji in text:
            text = text.replace(emoji, glyph)
    return text


def tr(language: str, text: str) -> str:
    """Translate a fixed TUI string via `kernel/i18n` and keep TUI emoji icons."""
    return restyle_text(i18n.tr(language, to_kernel_glyphs(text)))


def tr_text(language: str, text: str) -> str:
    """Translate dynamic TUI text via `kernel/i18n` and keep TUI emoji icons."""
    return restyle_text(i18n.tr_text(language, to_kernel_glyphs(text)))
