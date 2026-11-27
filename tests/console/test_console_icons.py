"""TUI icon layer: the owner's symbol set, one cell each, idempotent restyling and i18n lookup."""

from __future__ import annotations

from rich.cells import cell_len
from rich.console import Console
from rich.text import Text

from harness.console.kernel import brand, status
from harness.console.tui import chrome, icons
from harness.console.tui.screens.board import BoardScreen
from harness.console.tui.screens.dashboard import DashboardScreen
from harness.console.tui.screens.publish import PublishScreen
from harness.console.tui.screens.worker_observation import (
    CHIP_WIDTH,
    EVENT_KINDS,
    _PROCESS_WORDS,
    _STAGE_RESULTS,
    transcript_row,
)


def test_every_tui_icon_is_one_cell_glyph_of_the_owners_set() -> None:
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
        *icons.ROLE_ICONS.values(),
        icons.ROLE_FALLBACK,
    ]
    assert len(icons.GLYPHS) == 28
    for glyph in all_icons:
        # One codepoint of the set, one cell in Rich and in the terminal: no VS16, no emoji, so
        # borders and the space after an icon stay where Rich puts them.
        assert glyph in icons.GLYPHS, repr(glyph)
        # A glyph the VS Code terminal squeezes into one cell reads as an oval or a sliver.
        assert glyph not in icons.SQUEEZED, repr(glyph)
        assert "\ufe0f" not in glyph, repr(glyph)
        assert len(glyph) == 1, repr(glyph)
        assert cell_len(glyph) == 1, repr(glyph)
        assert cell_len(f" {glyph} ") == CHIP_WIDTH, repr(glyph)

    console = Console(width=40, record=True, color_system=None)
    for kind in (*EVENT_KINDS, "unknown-kind"):
        console.print(transcript_row({"kind": kind, "text": "ok"}))
    rendered = console.export_text()
    assert "…" not in rendered


def test_icon_to_text_spacing_in_top_bar_and_fixed_width_icon_widgets() -> None:
    plain = Text.from_markup(chrome.health_counts_markup((42, 1, 2, 11))).plain
    assert plain == "✦ 42  ✤ 1  ✖ 2  ⁘ 11"
    assert "margin-right: 1;" in DashboardScreen.DEFAULT_CSS.split(".problem-symbol")[1].split("}")[0]
    assert "margin-right: 1;" in BoardScreen.CSS.split("#board-live")[1].split("}")[0]
    assert "margin: 0 1;" in PublishScreen.CSS.split("#publish-live")[1].split("}")[0]


def test_restyle_text_is_idempotent_and_preserves_kernel_constants() -> None:
    assert brand.STATUS_ICONS == {"ok": "✔", "warn": "⚠", "fail": "✖", "skipped": "○"}
    assert status.KINDS["running"][0] == "▶"

    sample = "✔ ок · ⚠ внимание · ✖ сбой · ○ нет · ▶ в работе · Ⅱ пауза · ⊘ удаление"
    styled = icons.restyle_text(sample)
    assert styled == "✦ ок · ✤ внимание · ✖ сбой · ⁘ нет · ► в работе · ⁖ пауза · ▿ удаление"
    assert icons.restyle_text(styled) == styled
    assert icons.to_kernel_glyphs(styled) == sample


def test_tui_translation_maps_icon_strings_through_kernel_i18n() -> None:
    assert icons.tr("en", "◃ Остановить") == "◃ Stop"
    assert icons.tr("en", "◈ КОНТЕКСТ ЗАПУСКА") == "◈ LAUNCH CONTEXT"
    assert icons.tr("en", "⁘ Ожидание") == "⁘ Waiting"
    assert icons.tr("en", "Рекомендация (⁕):") == "Recommendation (⁕):"
    assert icons.tr_text("en", "✦ обратимо") == "✦ reversible"
    assert icons.tr_text("en", "▿ удаление") == "▿ deletion"
    assert icons.tr_text("en", "✖ заблокировано: {}") == "✖ blocked: {}"
    assert (
        icons.tr_text(
            "en",
            "✤ Наблюдение недоступно; исход процесса неизвестен. Повторный worker не запускается.",
        )
        == "Warning: observation unavailable; worker outcome unknown. No second worker is started."
    )


def test_every_loading_line_uses_the_one_running_icon() -> None:
    from harness.console.tui import icons

    assert icons.LOADING == icons.STATUS_KIND_ICONS["running"]
    assert icons.loading("Загрузка…") == f"{icons.LOADING} Загрузка…"


def test_a_line_after_a_status_icon_keeps_its_translation() -> None:
    from harness.console.tui import icons

    board = icons.tr_text("en", icons.loading("Читаю доску…"))
    assert icons.tr("en", icons.loading("Загрузка…")) == f"{icons.LOADING} Loading…"
    assert board == f"{icons.LOADING} Reading the board…"
    # A text the table knows whole is still translated whole.
    assert icons.tr("en", "Загрузка…") == "Loading…"


def test_a_role_is_one_icon_in_its_colour() -> None:
    assert icons.role_icon("architect") == ("◈", brand.ROLE_COLORS["architect"])
    assert icons.role_icon("developer") == ("✎", brand.ROLE_COLORS["developer"])
    # The ledger's `review` is the `code-review` role of the colour table.
    assert icons.role_icon("review") == ("∴", brand.ROLE_COLORS["code-review"])
    assert icons.role_icon("qa") == ("✚", brand.ROLE_COLORS["qa"])
    assert icons.role_icon("coordinator") == ("⁙", brand.PALETTE["primary"])
    assert icons.role_icon("database-migrations") == (icons.ROLE_FALLBACK, brand.PALETTE["muted"])
    assert icons.role_icon("-")[0] == ""
    assert icons.role_icon("")[0] == ""
    # Every role of the colour table has its own icon.
    assert set(brand.ROLE_COLORS) <= set(icons.ROLE_ICONS)


def test_a_dispatch_uuid_reads_as_d_and_its_first_eight_digits() -> None:
    text = "architect: dispatch-8e030c3f-336a-49db-b0a4-d8bc20022496, итог: reported"
    assert brand.short_dispatch(text) == "architect: d8e030c3f, итог: reported"
    # An id that is not a dispatch UUID keeps its form.
    assert brand.short_dispatch("dispatch-dev-887 · d-qa") == "dispatch-dev-887 · d-qa"
