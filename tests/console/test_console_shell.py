"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

# ruff: noqa: E402 — optional Textual imports follow importorskip.
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.binding import Binding

from harness.console.kernel.data import DashboardData
from harness.console.tui.screens.dashboard import DashboardScreen
from harness.console.tui.crumbs import Crumb
from harness.console.tui.wrap import SEPARATORS
from harness.console.tui.app import HarnessConsoleApp
from harness.console.kernel.data import DashboardData
from harness.console.tui.screens.dashboard import DashboardScreen
from harness.console.tui.crumbs import Crumb
from harness.console.tui.wrap import SEPARATORS
from tests.console._home_client import fake_home
from tests.console._pilot_wait import crumb_text
from harness.console.tui.shell import (
    SECTIONS,
    ConsoleShell,
)


def _home_data() -> DashboardData:
    return DashboardData(
        ok=5,
        warn=0,
        fail=2,
        skipped=1,
        repo_map_tier="Repo Map: tier=full (offline parser bundle detected)",
        harness_version="9.9.9",
        drift_state="drift",
        active_batches=3,
        problems=(
            ("fail", "files.skill_snapshot", "snapshot differs"),
            ("fail", "files.integrations", "integrations need a check"),
        ),
    )


def _home(tmp_path: Path) -> DashboardScreen:
    return DashboardScreen(
        tmp_path,
        home_client=fake_home(
            lambda _repo, *, online=False: _home_data(), repo=tmp_path
        ),
    )


def test_escape_on_home_keeps_the_screen_and_the_footer_has_no_back_key(
    tmp_path: Path,
) -> None:
    async def scenario() -> tuple[bool, list[str], list[str], bool]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            home = _home(tmp_path)
            await app.switch_screen(home)
            await pilot.pause()
            home_keys = _footer_keys(home)
            await pilot.press("escape")
            await pilot.pause()
            stayed = app.screen is home
            other = await _open(app, pilot)
            other_keys = _footer_keys(other)
            await pilot.press("escape")
            await pilot.pause()
            return stayed, home_keys, other_keys, app.screen is home

    stayed, home_keys, other_keys, back_home = asyncio.run(scenario())
    assert stayed
    assert "escape" not in home_keys
    assert "escape" in other_keys
    assert back_home


LONG_BRANCH = "feature/issue-721-console-design-system-with-a-long-tail"


def test_where_text_never_leaves_a_dangling_separator() -> None:
    from harness.console.tui.chrome import where_text

    assert where_text("project", None, 160) == "project"
    assert where_text("project", "", 80) == "project"
    assert where_text("project", "main", 160) == "project · ⎇ main"
    assert where_text("project", "main", 80) == "⎇ main"
    assert len(where_text("project", LONG_BRANCH, 80)) <= (80 - 4) // 2


def _color(widget: object) -> str:
    from textual.color import Color

    return Color.from_rich_color(widget.rich_style.color).hex.lower()  # type: ignore[attr-defined]


def test_shell_text_uses_the_foreground_token(tmp_path: Path) -> None:
    from harness.console.kernel import brand

    async def scenario() -> list[str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            home = _home(tmp_path)
            await app.switch_screen(home)
            await pilot.pause()
            colors = [
                _color(home.query_one("#topbar-left")),
                _color(home.query_one("#dashboard-offline")),
                _color(home.query_one("#dashboard-online")),
            ]
            screen = await _open(app, pilot)
            colors.append(_color(screen.query_one(".crumb-current")))
            return colors

    top, offline, online, crumb = asyncio.run(scenario())
    assert top == online == crumb == brand.PALETTE["foreground"].lower()
    # The current mode of the Offline | Online toggle is drawn in the selection colours.
    assert offline == brand.SHELL_TOKENS["selection-foreground"]


def test_the_shell_css_has_no_default_text_token() -> None:
    import re

    from harness.console.kernel import brand
    from harness.console.tui.chrome import WorkspaceHeader
    from harness.console.tui.shell import SHELL_CSS

    for css in (SHELL_CSS, WorkspaceHeader.DEFAULT_CSS, DashboardScreen.CSS):
        assert not re.search(r"\$text(?![\w-])", brand.shell_css(css))


@pytest.mark.parametrize("size", [(160, 52), (80, 24)])
def test_the_crumb_row_starts_with_the_menu_toggle_and_home_has_one_crumb(
    tmp_path: Path, size: tuple[int, int]
) -> None:
    async def scenario() -> tuple[str, bool, bool, str, str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=size) as pilot:
            home = _home(tmp_path)
            await app.switch_screen(home)
            await pilot.pause()
            row = home.query_one(".crumb-row")
            toggle = row.children[0]
            crumbs = home.query_one(Breadcrumbs)
            assert isinstance(toggle, Button) and toggle.id == "dashboard-menu"
            left_of_crumbs = toggle.region.right <= crumbs.region.x
            ru = crumb_text(crumbs)
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            return (
                str(toggle.label),
                toggle.display and left_of_crumbs,
                not home.query(".context-strip .menu-toggle"),
                ru,
                crumb_text(crumbs),
            )

    label, toggle_first, strip_free, ru, en = asyncio.run(scenario())
    assert label == "≡"
    assert toggle_first == (size[0] < 100)
    assert strip_free
    assert (ru, en) == ("Главная", "Home")


def _region_text(app: HarnessConsoleApp, widget: object) -> list[str]:
    """The cells `widget` occupies on screen, row by row, as plain text."""
    region = widget.region  # type: ignore[attr-defined]
    strips = app.screen._compositor.render_strips()
    lines = ["".join(segment.text for segment in strip) for strip in strips]
    return [line[region.x : region.right] for line in lines[region.y : region.bottom]]


def _menu_text(item: ListItem) -> str:
    """The number and name of a menu entry, without its badge."""
    label = item.query_one(Static).content
    return str(label.columns[0]._cells[0])  # type: ignore[union-attr]


def _menu_item(screen: ConsoleShell, name: str) -> ListItem:
    return next(
        item
        for item in screen.query("ShellSidebar ListItem").results(ListItem)
        if item.name == name
    )


@pytest.mark.parametrize("language", ["ru", "en"])
@pytest.mark.parametrize("size", [(160, 52), (100, 30), (80, 24)])
def test_the_main_menu_fits_update_harness_and_its_badge_on_one_line(
    tmp_path: Path, size: tuple[int, int], language: str
) -> None:
    from harness.console.kernel import brand

    async def scenario() -> tuple[int, str, list[str], list[str], object]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=size) as pilot:
            home = _home(tmp_path)
            await app.switch_screen(home)
            await pilot.pause()
            if language == "en":
                await pilot.press("f2")
                await pilot.pause()
            if size[0] < 100:
                await pilot.click("#dashboard-menu")
                await pilot.pause()
            sidebar = home.query_one(ShellSidebar)
            update = _menu_item(home, "Update Harness").query_one(Static)
            selected = _menu_item(home, "Home")
            return (
                sidebar.region.width,
                str(sidebar.query_one(".menu-heading", Static).render()),
                _region_text(app, update),
                _region_text(app, selected.query_one(Static)),
                selected.styles,
            )

    width, heading, update, selected, styles = asyncio.run(scenario())
    # 27 columns between 100 and 140 columns, where the content needs the room.
    assert width == (27 if 100 <= size[0] < 140 else 30)
    assert heading == ("ГЛАВНОЕ МЕНЮ" if language == "ru" else "MAIN MENU")
    label = "2 Обновить Harness" if language == "ru" else "2 Update Harness"
    assert len(update) == 1
    assert update[0].startswith(label) and update[0].rstrip().endswith("⚠")
    assert selected[0].startswith("0 ")
    # The selected entry: the selection fill, an outline on a wide terminal, no left bar.
    tokens = brand.SHELL_TOKENS
    assert styles.background.hex.lower() == tokens["selection-background"]  # type: ignore[attr-defined]
    assert styles.border_left[0] in ("", "none")  # type: ignore[attr-defined]
    outline = styles.outline_top  # type: ignore[attr-defined]
    if size[1] >= 38:
        assert outline[0] == "round"
        assert outline[1].hex.lower() == tokens["selection-outline"]
    else:
        assert outline[0] in ("", "none")


def test_a_menu_number_takes_the_colour_of_its_entry() -> None:
    from rich.text import Text

    from harness.console.tui.shell import menu_label

    label = menu_label(2, "Update Harness", ("⚠", "#E5A04B"))
    name, badge = (column._cells[0] for column in label.columns)
    assert isinstance(name, Text) and name.plain == "2 Обновить Harness"
    assert not name.style and not name.spans
    assert isinstance(badge, Text) and badge.plain.strip() == "⚠"


def test_section_badges_come_from_the_health_facts() -> None:
    from harness.console.kernel import brand
    from harness.console.tui.shell import section_badges

    badges = section_badges(_home_data())
    assert badges == {
        "Diagnostics": ("✖ 2", brand.STATUS_COLORS["fail"]),
        "Harness": ("⚠", brand.STATUS_COLORS["warn"]),
        "Update Harness": ("⚠", brand.STATUS_COLORS["warn"]),
        "Orchestration": ("3", brand.PALETTE["muted"]),
        "Repo Map": ("full", brand.STATUS_COLORS["ok"]),
    }
    clean = DashboardData(
        ok=1,
        warn=1,
        fail=0,
        skipped=0,
        repo_map_tier="Repo Map не установлен в проект",
        harness_version="9.9.9",
        drift_state="clean",
        active_batches=None,
    )
    assert section_badges(clean) == {
        "Diagnostics": ("⚠ 1", brand.STATUS_COLORS["warn"]),
        "Harness": ("✔", brand.STATUS_COLORS["ok"]),
    }


def test_the_menu_badges_are_shown_on_another_shell_screen(tmp_path: Path) -> None:
    from harness.console.tui.screens.diagnostics import DiagnosticsScreen
    from harness.health.model import Report

    report = Report(schema_version=1, repo=str(tmp_path), online=False, checks=[])

    async def scenario() -> tuple[list[str], list[str]]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            await app.switch_screen(_home(tmp_path))
            await pilot.pause()
            diagnostics = DiagnosticsScreen(
                tmp_path, collect_diagnostics=lambda _repo, *, online=False: report
            )
            await app.push_screen(diagnostics)
            await pilot.pause()
            await pilot.pause()
            return (
                _region_text(
                    app, _menu_item(diagnostics, "Diagnostics").query_one(Static)
                ),
                _region_text(
                    app, _menu_item(diagnostics, "Orchestration").query_one(Static)
                ),
            )

    diagnostics, orchestration = asyncio.run(scenario())
    assert diagnostics[0].startswith("3 Диагностика")
    assert diagnostics[0].rstrip().endswith("✖ 2")
    assert orchestration[0].rstrip().endswith("3")


def test_a_section_title_is_in_capitals_with_its_note_after_it() -> None:
    from harness.console.kernel import brand, i18n

    assert brand.section_title("Требует внимания", "2") == " ТРЕБУЕТ ВНИМАНИЯ  2 "
    assert brand.section_title(" Действия ") == " ДЕЙСТВИЯ "
    # A title in capitals still finds its English text.
    assert i18n.tr("en", "HEALTH-ОТЧЁТ") == "HEALTH REPORT"
    assert i18n.tr("en", "СОСТОЯНИЕ · 3") == "STATUS · 3"
    assert i18n.tr("ru", "HEALTH-ОТЧЁТ") == "HEALTH-ОТЧЁТ"


class CardShell(StubShell):
    """A shell screen whose page is one section card and one fold."""

    def compose_content(self) -> ComposeResult:
        yield SectionCard(
            Static("Содержимое", id="card-body"),
            title="Проверки",
            note="3",
            id="stub-card",
        )
        yield Fold(
            Static("Подробности", id="fold-body"),
            title="Подробный отчёт",
            summary="27 проверок · 11 пропущено",
            id="stub-fold",
        )


def test_section_cards_and_folds_follow_the_language_with_muted_titles(
    tmp_path: Path,
) -> None:
    from textual.widgets._collapsible import CollapsibleTitle

    from harness.console.kernel import brand

    async def scenario() -> tuple[list[str], list[str], str, bool]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            screen = CardShell()
            await app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            card = screen.query_one("#stub-card", SectionCard)
            fold = screen.query_one("#stub-fold", Fold)
            title = fold.query_one(CollapsibleTitle)

            def texts() -> list[str]:
                return [str(card.border_title), str(title.render())]

            ru = texts()
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            en = texts()
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            assert texts() == ru
            title.focus()
            await pilot.press("enter")
            await pilot.pause()
            return ru, en, card.styles.border_title_color.hex, not fold.collapsed

    ru, en, color, opened = asyncio.run(scenario())
    assert ru[0] == " ПРОВЕРКИ  3 "
    # The summary sits at the right end of the fold's title row.
    assert ru[1].startswith("▸ Подробный отчёт  ")
    assert ru[1].endswith("  27 проверок · 11 пропущено")
    assert len(ru[1]) > len("▸ Подробный отчёт  27 проверок · 11 пропущено") + 20
    assert en[0] == " CHECKS  3 " and en[1].startswith("▸ Detailed report  ")
    assert color.lower() == brand.PALETTE["muted"].lower()
    assert opened


def test_frame_titles_of_shell_screens_are_muted_capitals(tmp_path: Path) -> None:
    from harness.console.kernel import brand
    from harness.console.tui.screens.diagnostics import DiagnosticsScreen
    from harness.health.model import Report

    report = Report(schema_version=1, repo=str(tmp_path), online=False, checks=[])

    async def scenario() -> tuple[str, str, str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            screen = DiagnosticsScreen(
                tmp_path, collect_diagnostics=lambda _repo, *, online=False: report
            )
            await app.push_screen(screen)
            await pilot.pause()
            frame = screen.query_one("#diagnostics-scroll")
            ru = str(frame.border_title)
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            return ru, str(frame.border_title), frame.styles.border_title_color.hex

    ru, en, color = asyncio.run(scenario())
    assert (ru, en) == (" HEALTH-ОТЧЁТ ", " HEALTH REPORT ")
    assert color.lower() == brand.PALETTE["muted"].lower()


@pytest.mark.parametrize("size", [(160, 52), (80, 24)])
def test_a_narrow_footer_shows_the_mockup_keys_and_hidden_keys_still_work(
    tmp_path: Path, size: tuple[int, int]
) -> None:
    calls: list[bool] = []

    def collect(_repo: Path, *, online: bool = False) -> DashboardData:
        calls.append(online)
        return _home_data()

    async def scenario() -> set[str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=size) as pilot:
            home = DashboardScreen(
                tmp_path, home_client=fake_home(collect, repo=tmp_path)
            )
            await app.switch_screen(home)
            await pilot.pause()
            keys = set(_footer_keys(home)) - {app.COMMAND_PALETTE_BINDING}
            await pilot.press("r")
            await app.workers.wait_for_complete()
            await pilot.pause()
            return keys

    keys = asyncio.run(scenario())
    assert keys == ({"p", "f1", "f2"} if size[0] < 100 else {"r", "o", "p", "f1", "f2"})
    # `r` is not in the narrow footer, but it still reruns the offline checks.
    assert calls == [False, False]


def test_the_footer_follows_a_resize_across_the_narrow_threshold(
    tmp_path: Path,
) -> None:
    async def scenario() -> tuple[set[str], set[str]]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(160, 52)) as pilot:
            home = _home(tmp_path)
            await app.switch_screen(home)
            await pilot.pause()
            wide = set(_footer_keys(home))
            await pilot.resize_terminal(80, 24)
            await pilot.pause()
            await pilot.pause()
            return wide, set(_footer_keys(home))

    wide, narrow = asyncio.run(scenario())
    assert {"r", "o"} <= wide
    assert not {"r", "o"} & narrow and "p" in narrow


def test_every_health_check_has_a_readable_title_and_a_menu_section() -> None:
    from harness.console.kernel import i18n
    from harness.console.tui.shell import CHECK_ROUTES, check_route
    from harness.health.registry import REGISTRY

    ids = [check_id for check_id, _check in REGISTRY]
    assert set(ids) == set(CHECK_ROUTES)
    for check_id in ids:
        route = check_route(check_id)
        assert route.section in SECTIONS and route.section != "Home", check_id
        assert route.title != check_id
        assert i18n.tr("en", route.title) != route.title, route.title
    assert check_route("files.skill_snapshot").section == "Update Harness"
    assert check_route("files.integrations").section == "Configuration"
    unknown = check_route("net.something")
    assert (unknown.title, unknown.section) == ("net.something", "Diagnostics")


def test_a_jump_is_labelled_by_its_section_or_its_action() -> None:
    from harness.console.kernel import i18n

    assert i18n.jump_label("ru", "Update Harness") == "Обновить Harness"
    assert i18n.jump_label("en", "Update Harness") == "Update Harness"
    assert i18n.jump_label("ru", "Configuration") == "Открыть настройку"
    assert i18n.jump_label("en", "Configuration") == "Open setup"


class JumpShell(StubShell):
    def compose_content(self) -> ComposeResult:
        yield JumpLink("Update Harness", id="jump-update")
        yield JumpLink("Configuration", id="jump-configuration")


@pytest.mark.parametrize("how", ["click", "enter"])
def test_a_jump_link_opens_its_section_and_runs_no_command(
    tmp_path: Path, how: str
) -> None:
    from harness.console.tui.screens.update_harness import UpdateHarnessScreen

    recorder = _Recorder()

    async def scenario() -> tuple[list[str], list[str], bool]:
        app = HarnessConsoleApp(tmp_path, command_runner=recorder)
        async with app.run_test(size=(160, 52)) as pilot:
            await app.switch_screen(
                DashboardScreen(
                    tmp_path,
                    home_client=fake_home(
                        lambda _repo, *, online=False: _home_data(), repo=tmp_path
                    ),
                    command_runner=recorder,
                )
            )
            await pilot.pause()
            screen = JumpShell()
            await app.push_screen(screen)
            await pilot.pause()
            links = [str(link.render()) for link in screen.query(JumpLink)]
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            english = [str(link.render()) for link in screen.query(JumpLink)]
            if how == "click":
                await pilot.click("#jump-update")
            else:
                screen.query_one("#jump-update", JumpLink).focus()
                await pilot.press("enter")
            for _ in range(3):
                await pilot.pause()
            return links, english, isinstance(app.screen, UpdateHarnessScreen)

    links, english, opened = asyncio.run(scenario())
    assert links == ["Обновить Harness  2 →", "Открыть настройку  8 →"]
    assert english == ["Update Harness  2 →", "Open setup  8 →"]
    assert opened
    assert recorder.calls == []


def test_a_jump_link_shows_only_the_number_on_a_narrow_terminal(
    tmp_path: Path,
) -> None:
    async def scenario() -> list[str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = JumpShell()
            await app.push_screen(screen)
            await pilot.pause()
            return [str(link.render()) for link in screen.query(JumpLink)]

    assert asyncio.run(scenario()) == ["2 →", "8 →"]


def test_language_switch_relabels_menu_and_breadcrumbs(tmp_path: Path) -> None:
    async def scenario() -> tuple[list[str], str, list[str], str]:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open(app, pilot)

            def labels() -> list[str]:
                return [
                    _menu_text(item)
                    for item in screen.query("#stub-sections > ListItem").results(
                        ListItem
                    )
                ]

            def crumbs() -> str:
                return crumb_text(screen.query_one("#shell-breadcrumbs", Breadcrumbs))

            before = labels(), crumbs()
            await pilot.press("f2")
            await pilot.pause()
            await pilot.pause()
            return before[0], before[1], labels(), crumbs()

    ru_labels, ru_crumbs, en_labels, en_crumbs = asyncio.run(scenario())
    assert ru_labels[5] == "5 Оркестрация" and ru_crumbs == "Главная  ›  Отчёты"
    assert en_labels[5] == "5 Orchestration" and en_crumbs == "Home  ›  Reports"
    assert ru_labels[0] == "0 Главная" and en_labels[0] == "0 Home"


def test_home_is_item_zero_and_keys_one_to_nine_keep_their_sections() -> None:
    assert SECTIONS == (
        "Home",
        "Open project",
        "Update Harness",
        "Diagnostics",
        "Harness",
        "Orchestration",
        "Reports",
        "Repo Map",
        "Configuration",
        "Help",
    )
    actions = {
        binding.key: binding.action
        for binding in ConsoleShell.BINDINGS
        if isinstance(binding, Binding)
    }
    for number in range(10):
        assert actions[str(number)] == f"section({number})"


def test_the_shell_screens_carry_no_local_colours_top_bar_or_number_keys() -> None:
    """The Home, Open project, Diagnostics, Harness, Reports, Repo Map and Configuration screens
    take colours, the top bar and the navigation from the shell: their sources hold none of their
    own, and the Configuration screens bind no Esc themselves (the shell's `action_back` is the
    only Esc binding)."""
    import re

    from harness.console.tui.screens.configuration import ConfigurationScreen
    from harness.console.tui.screens.configuration_versions import (
        ConfigurationVersionsScreen,
    )
    from harness.console.tui.screens.project_setup import ProjectSetupScreen
    from harness.console.tui.screens.update_harness import UpdateHarnessScreen

    from harness.console.tui.screens.project_setup import ProjectSetupScreen
    from harness.console.tui.screens.update_harness import UpdateHarnessScreen

    for screen_class in (
        ConfigurationScreen,
        ConfigurationVersionsScreen,
        UpdateHarnessScreen,
        ProjectSetupScreen,
    ):
        assert issubclass(screen_class, ConsoleShell)
        own = screen_class.__dict__.get("BINDINGS", [])
        keys = [b.key if isinstance(b, Binding) else b[0] for b in own]
        assert "escape" not in keys, screen_class

    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "tui" / "screens"
    names = (
        "dashboard",
        "harness",
        "diagnostics",
        "project_setup",
        "commands",
        "reports",
        "repo_map",
        "repo_map_settings",
        "configuration",
        "configuration_versions",
        "update_harness",
    )
    for name in names:
        source = (screens / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"#[0-9A-Fa-f]{6}\b", source), f"{name}: a hex colour"
        assert not re.search(r"Binding\(\s*[\"']\d", source), f"{name}: a number key"
        if name != "commands":
            # `CommandMenuScreen.compose` is the one left-over of the old frame (no screen uses it).
            assert "TopBar(" not in source, f"{name}: a top bar of its own"
        # `configuration` is left out: its confirmation modal binds its own Esc (a modal has no frame).
        if name in ("configuration_versions", "update_harness", "project_setup"):
            assert not re.search(
                r"Binding\(\s*[\"']escape", source
            ), f"{name}: its own Esc binding"


def test_reports_and_repo_map_leave_back_and_breakpoints_to_the_shell() -> None:
    """Esc and the narrow layout belong to the shell: these screens add neither a back key nor
    breakpoints of their own (the build confirmation is a modal, with its own cancel)."""
    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "tui" / "screens"
    for name, modals in (("reports", 0), ("repo_map", 1), ("repo_map_settings", 0)):
        source = (screens / f"{name}.py").read_text(encoding="utf-8")
        assert source.count('Binding("escape"') == modals, f"{name}: an Esc binding"
        assert "HORIZONTAL_BREAKPOINTS" not in source, f"{name}: breakpoints of its own"
        assert "app.pop_screen" not in source, f"{name}: a back action of its own"


def test_reports_and_repo_map_show_no_demo_data_from_the_mockups() -> None:
    """The mockups' sample values (ids, commits, paths, counts) are not in the screens' sources."""
    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "tui" / "screens"
    demo = (
        "85abd57e",
        "generation-1e1684b3",
        "698fa45a",
        "555837f4",
        "issue-721-console-design-system",
        "cp312-linux_x86_64",
        "legacy_gen.py",
        "PVMalove",
        "tree-sitter",
    )
    for name in ("reports", "repo_map", "repo_map_settings"):
        source = (screens / f"{name}.py").read_text(encoding="utf-8")
        for value in demo:
            assert value not in source, f"{name}: the mockup's sample {value!r}"


def test_the_mockup_legend_functions_are_not_on_the_reports_screens(
    tmp_path: Path,
) -> None:
    """The section table of contents, the event-type filter and “Сбросить” are the mockup's own
    suggestions, left for a follow-up ticket: no screen of Reports has them."""
    from textual.widgets import Input, Select

    from harness.console.tui.screens.reports import (
        BatchTimelineScreen,
        QaLogsScreen,
        ReportScreen,
        ReportsScreen,
    )
    from tests.console._console_ledger_fixture import build_reports_fixture

    build_reports_fixture(tmp_path)
    from harness.console.tui.reports import load_ledger_view

    view = load_ledger_view(tmp_path)
    entry = view.reports[0]
    timeline = view.timeline(entry.batch_id)
    assert timeline is not None
    forbidden = ("Сбросить", "Reset", "Разделы", "Оглавление", "Типы событий")

    async def scenario() -> dict[str, tuple[str, int, int, int]]:
        found: dict[str, tuple[str, int, int, int]] = {}
        for name, make in (
            ("list", lambda: ReportsScreen(tmp_path)),
            ("report", lambda: ReportScreen(entry, view, tmp_path)),
            ("timeline", lambda: BatchTimelineScreen(timeline, tmp_path)),
            ("qa", lambda: QaLogsScreen(view)),
        ):
            screen = make()

            class Host(App[None]):
                def on_mount(self) -> None:
                    self.push_screen(screen)

            app = Host()
            async with app.run_test(size=(160, 52)) as pilot:
                await pilot.pause()
                text = "\n".join(
                    [str(w.content) for w in app.screen.query(Static)]
                    + [str(b.label) for b in app.screen.query(Button)]
                    + [str(c.border_title) for c in app.screen.query(SectionCard)]
                )
                found[name] = (
                    text,
                    len(app.screen.query(Input)),
                    len(app.screen.query(Select)),
                    len(app.screen.query(Button)),
                )
        return found

    found = asyncio.run(scenario())
    for name, (text, _, _, _) in found.items():
        for word in forbidden:
            assert word not in text, f"{name}: {word!r}"
    # Only the list has filters (five texts, three choices); the other screens have none.
    assert found["list"][1:3] == (5, 3)
    assert found["report"][1:3] == (0, 0)
    assert found["timeline"][1:3] == (0, 0)
    assert found["qa"][1:3] == (0, 0)
