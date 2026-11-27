"""TUI emoji icon layer: uniform cell width, idempotent restyling and i18n lookup."""

from __future__ import annotations

from rich.cells import cell_len
from rich.console import Console

from harness.console.kernel import brand, status
from harness.console.tui import icons
from harness.console.tui.screens.worker_observation import (
    CHIP_WIDTH,
    EVENT_KINDS,
    _PROCESS_WORDS,
    _STAGE_RESULTS,
    transcript_row,
)


def test_every_tui_emoji_icon_is_two_cells_wide_and_fits_a_worker_chip() -> None:
    all_icons = [
        *icons.STATUS_ICONS.values(),
        *icons.STATUS_KIND_ICONS.values(),
        *icons.CONTEXT_ICONS.values(),
        icons.CONTEXT_FALLBACK,
        icons.STOP,
        icons.REFRESH,
        icons.BRANCH,
        icons.STAR,
        icons.LAUNCH_CONTEXT,
        icons.DELETE,
        icons.PLAIN_LOG,
        icons.UNKNOWN,
        icons.LIVE_ON,
        icons.LIVE_OFF,
        *(glyph for glyph, *_ in EVENT_KINDS.values()),
        *(glyph for glyph, *_ in _STAGE_RESULTS.values()),
        *(glyph for glyph, *_ in _PROCESS_WORDS.values()),
    ]
    for glyph in all_icons:
        assert cell_len(glyph) == 2, repr(glyph)
        assert cell_len(f" {glyph} ") == CHIP_WIDTH, repr(glyph)

    console = Console(width=40, record=True, color_system=None)
    for kind in (*EVENT_KINDS, "unknown-kind"):
        console.print(transcript_row({"kind": kind, "text": "ok"}))
    rendered = console.export_text()
    assert "…" not in rendered


def test_restyle_text_is_idempotent_and_preserves_kernel_constants() -> None:
    assert brand.STATUS_ICONS == {"ok": "✔", "warn": "⚠", "fail": "✖", "skipped": "○"}
    assert status.KINDS["running"][0] == "▶"

    sample = "✔ ок · ⚠ внимание · ✖ сбой · ○ нет · ▶ в работе · Ⅱ пауза · ⊘ удаление"
    styled = icons.restyle_text(sample)
    assert styled == "✅ ок · ⚠️ внимание · ❌ сбой · ⚪ нет · ▶️ в работе · ⏸️ пауза · 🗑️ удаление"
    assert icons.restyle_text(styled) == styled
    assert icons.to_kernel_glyphs(styled) == sample


def test_tui_translation_maps_emoji_strings_through_kernel_i18n() -> None:
    assert icons.tr("en", "⏹️ Остановить") == "⏹️ Stop"
    assert icons.tr("en", "🎯 КОНТЕКСТ ЗАПУСКА") == "🎯 LAUNCH CONTEXT"
    assert icons.tr("en", "⚪ Ожидание") == "⚪ Waiting"
    assert icons.tr("en", "Рекомендация (⭐):") == "Recommendation (⭐):"
    assert icons.tr_text("en", "✅ обратимо") == "✅ reversible"
    assert icons.tr_text("en", "🗑️ удаление") == "🗑️ deletion"
    assert (
        icons.tr_text(
            "en",
            "⚠️ Наблюдение недоступно; исход процесса неизвестен. Повторный worker не запускается.",
        )
        == "Warning: observation unavailable; worker outcome unknown. No second worker is started."
    )
