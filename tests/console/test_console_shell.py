"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

# ruff: noqa: E402 — optional Textual imports follow importorskip.
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.binding import Binding

from harness.console.data import DashboardData
from harness.console.screens.dashboard import DashboardScreen
from harness.console.shell import (
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


LONG_BRANCH = "feature/issue-721-console-design-system-with-a-long-tail"


def test_where_text_never_leaves_a_dangling_separator() -> None:
    from harness.console.chrome import where_text

    assert where_text("project", None, 160) == "project"
    assert where_text("project", "", 80) == "project"
    assert where_text("project", "main", 160) == "project · ⎇ main"
    assert where_text("project", "main", 80) == "⎇ main"
    assert len(where_text("project", LONG_BRANCH, 80)) <= (80 - 4) // 2


def test_the_shell_css_has_no_default_text_token() -> None:
    import re

    from harness.console import brand
    from harness.console.chrome import WorkspaceHeader
    from harness.console.shell import SHELL_CSS

    for css in (SHELL_CSS, WorkspaceHeader.DEFAULT_CSS, DashboardScreen.CSS):
        assert not re.search(r"\$text(?![\w-])", brand.shell_css(css))


def test_a_menu_number_takes_the_colour_of_its_entry() -> None:
    from rich.text import Text

    from harness.console.shell import menu_label

    label = menu_label(2, "Update Harness", ("⚠", "#E5A04B"))
    name, badge = (column._cells[0] for column in label.columns)
    assert isinstance(name, Text) and name.plain == "2 Обновить Harness"
    assert not name.style and not name.spans
    assert isinstance(badge, Text) and badge.plain.strip() == "⚠"


def test_section_badges_come_from_the_health_facts() -> None:
    from harness.console import brand
    from harness.console.shell import section_badges

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


def test_a_section_title_is_in_capitals_with_its_note_after_it() -> None:
    from harness.console import brand, i18n

    assert brand.section_title("Требует внимания", "2") == " ТРЕБУЕТ ВНИМАНИЯ  2 "
    assert brand.section_title(" Действия ") == " ДЕЙСТВИЯ "
    # A title in capitals still finds its English text.
    assert i18n.tr("en", "HEALTH-ОТЧЁТ") == "HEALTH REPORT"
    assert i18n.tr("en", "СОСТОЯНИЕ · 3") == "STATUS · 3"
    assert i18n.tr("ru", "HEALTH-ОТЧЁТ") == "HEALTH-ОТЧЁТ"


def test_every_health_check_has_a_readable_title_and_a_menu_section() -> None:
    from harness.console import i18n
    from harness.console.shell import CHECK_ROUTES, check_route
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
    from harness.console import i18n

    assert i18n.jump_label("ru", "Update Harness") == "Обновить Harness"
    assert i18n.jump_label("en", "Update Harness") == "Update Harness"
    assert i18n.jump_label("ru", "Configuration") == "Открыть настройку"
    assert i18n.jump_label("en", "Configuration") == "Open setup"


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

    from harness.console.screens.configuration import ConfigurationScreen
    from harness.console.screens.configuration_versions import (
        ConfigurationVersionsScreen,
    )
    from harness.console.screens.project_setup import ProjectSetupScreen
    from harness.console.screens.update_harness import UpdateHarnessScreen

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

    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "screens"
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
    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "screens"
    for name, modals in (("reports", 0), ("repo_map", 1), ("repo_map_settings", 0)):
        source = (screens / f"{name}.py").read_text(encoding="utf-8")
        assert source.count('Binding("escape"') == modals, f"{name}: an Esc binding"
        assert "HORIZONTAL_BREAKPOINTS" not in source, f"{name}: breakpoints of its own"
        assert "app.pop_screen" not in source, f"{name}: a back action of its own"


def test_reports_and_repo_map_show_no_demo_data_from_the_mockups() -> None:
    """The mockups' sample values (ids, commits, paths, counts) are not in the screens' sources."""
    screens = Path(__file__).resolve().parents[2] / "harness" / "console" / "screens"
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
