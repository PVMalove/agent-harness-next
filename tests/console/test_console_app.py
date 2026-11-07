"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("textual")

from harness.console.kernel import brand
from harness.console.kernel.data import DashboardData
from harness.console.tui.screens.dashboard import DashboardScreen
from harness.health.model import CheckResult, Fix, Report
from tests.console._home_client import fake_home


def _fake_dashboard_data() -> DashboardData:
    """Сформировать тестовые данные для экрана дашборда."""
    return DashboardData(
        ok=5,
        warn=1,
        fail=0,
        skipped=2,
        repo_map_tier="full",
        harness_version="9.9.9",
        drift_state="clean",
        active_batches=3,
    )


def _fake_report(
    *, online: bool = False, fixes_applied: list[str] | None = None
) -> Report:
    """Сформировать тестовый отчёт диагностики."""
    return Report(
        schema_version=1,
        repo="/tmp/fake-repo",
        online=online,
        checks=[
            CheckResult(id="files.lock", group="files", status="ok", message="lock ok"),
            CheckResult(
                id="environment.uv",
                group="environment",
                status="fail",
                message="uv недоступен",
                fix=Fix(text="поставить uv", command="echo installing-uv"),
            ),
        ],
        fixes_applied=fixes_applied or [],
    )


def test_dashboard_summary_lists_problems_and_splits_repo_map_facts() -> None:
    """Проверить, что сводка перечисляет ошибки и предупреждения и разбивает строку Repo Map."""
    from dataclasses import replace

    from rich.text import Text

    from harness.console.tui.screens.dashboard import _render_summary

    data = replace(
        _fake_dashboard_data(),
        repo_map_tier="tier=minimal; policy: enforced",
        problems=(
            ("fail", "env.git", "git [bold] missing"),
            ("warn", "repo_map.tier", "minimal"),
        ),
    )
    text = _render_summary(data)
    plain = Text.from_markup(text).plain
    assert "repo map: tier=minimal\n  policy: enforced" in plain
    assert "ошибки и предупреждения:" in plain
    assert "env.git — git \\[bold] missing" in text
    assert text.index("env.git") < text.index("repo_map.tier —")


def test_dashboard_summary_colors_labels_and_normalizes_repo_map() -> None:
    from dataclasses import replace

    from rich.color import Color
    from rich.style import Style
    from rich.text import Text

    from harness.console.tui.screens.dashboard import _render_summary

    data = replace(
        _fake_dashboard_data(),
        repo_map_tier=(
            "Repo Map: tier=minimal (requested by policy); "
            "Repo Map provenance: policy requested path-only inventory; "
            "Repo Map policy: enforced; dispatch is limited to minimal path inventory"
        ),
    )
    rendered = Text.from_markup(_render_summary(data))
    assert "repo map: tier=minimal" in rendered.plain
    assert "  provenance: policy requested path-only inventory" in rendered.plain
    assert "  policy: enforced" in rendered.plain
    assert "Repo Map" not in rendered.plain
    for label in (
        "health (offline):",
        "active batches:",
        "repo map:",
        "memory:",
        "harness:",
    ):
        start = rendered.plain.index(label)
        assert any(
            span.start <= start
            and span.end >= start + len(label)
            and Style.parse(str(span.style)).bold
            and Style.parse(str(span.style)).color
            == Color.parse(brand.PALETTE["primary"])
            for span in rendered.spans
        )


@pytest.mark.parametrize("status", ["ok", "warn", "fail", "skipped"])
def test_dashboard_summary_shows_memory_health_without_interpreting_markup(
    status: str,
) -> None:
    from dataclasses import replace
    from typing import cast

    from rich.text import Text

    from harness.console.tui.screens.dashboard import _render_summary
    from harness.health.model import Status

    data = replace(
        _fake_dashboard_data(),
        memory_index=CheckResult(
            id="memory.index",
            group="memory",
            status=cast(Status, status),
            message="индекс [test]",
        ),
    )
    assert (
        f"memory: {brand.STATUS_ICONS[status]} {status} — индекс [test]"
        in Text.from_markup(_render_summary(data)).plain
    )


def test_dashboard_captures_command_output_by_default(tmp_path: Path) -> None:
    """Проверить, что дашборд без явного runner передаёт разделам перехватывающий runner,
    а не runner со сквозным выводом в терминал, которым владеет TUI."""
    from harness.console.kernel.runner import capturing_runner

    screen = DashboardScreen(
        tmp_path,
        home_client=fake_home(
            lambda _repo, *, online=False: _fake_dashboard_data(), repo=tmp_path
        ),
    )

    assert screen._command_runner is capturing_runner


def test_elapsed_time_and_check_counts_read_naturally() -> None:
    from datetime import UTC, datetime, timedelta

    from harness.console.kernel import i18n
    from harness.console.tui.session_card import elapsed_text

    now = datetime(2026, 10, 17, 14, 40, tzinfo=UTC)
    assert elapsed_text(now - timedelta(seconds=30), now, "ru") == "0 мин"
    assert elapsed_text(now - timedelta(minutes=14), now, "en") == "14 min"
    assert elapsed_text(now - timedelta(hours=3, minutes=5), now, "ru") == "3 ч"
    assert elapsed_text(now - timedelta(days=2, hours=1), now, "en") == "2 d"
    assert elapsed_text(None, now, "ru") == ""
    assert elapsed_text(now + timedelta(minutes=1), now, "ru") == ""
    assert i18n.checks_count("ru", 27, 11) == "27 проверок · 11 пропущено"
    assert i18n.checks_count("ru", 21, 0) == "21 проверка · 0 пропущено"
    assert i18n.checks_count("ru", 34, 2) == "34 проверки · 2 пропущено"
    assert i18n.checks_count("ru", 12, 2) == "12 проверок · 2 пропущено"
    assert i18n.checks_count("en", 1, 0) == "1 check · 0 skipped"
    assert i18n.checks_count("en", 27, 11) == "27 checks · 11 skipped"


def _mixed_report() -> Report:
    return Report(
        schema_version=1,
        repo="/tmp/fake-repo",
        online=False,
        checks=[
            CheckResult(id="files.lock", group="files", status="ok", message="lock ok"),
            CheckResult(id="env.node", group="env", status="warn", message="node old"),
            CheckResult(id="env.uv", group="env", status="fail", message="uv missing"),
            CheckResult(
                id="net.pypi", group="net", status="skipped", message="offline"
            ),
        ],
    )


def test_report_statuses_and_counters_are_shown_as_symbol_plus_text() -> None:
    from harness.console.tui.screens.diagnostics import _styled_report, render_report

    report = _mixed_report()
    before = render_report(report)
    shown = _styled_report(report).plain.split("\n")
    assert shown[0] == "Итого: ✔ ok=1 ⚠ warn=1 ✖ fail=1 ○ skipped=1"
    assert "✔ [OK] files.lock: lock ok" in shown
    assert "⚠ [WARN] env.node: node old" in shown
    assert "✖ [FAIL] env.uv: uv missing" in shown
    assert "○ - net.pypi: offline" in shown
    # Only the display changes: the report text and the export keep the plain markers.
    assert render_report(report) == before
    assert "✔" not in before and "✖" not in before
    english = _styled_report(report, "en").plain.split("\n")
    assert english[0].startswith("Total: ✔ ok=1") and "○ skipped=1" in english[0]


def test_a_zero_counter_keeps_its_symbol_and_is_muted() -> None:
    from harness.console.tui.screens.diagnostics import _styled_report

    shown = _styled_report(_fake_report())
    assert shown.plain.split("\n")[0] == "Итого: ✔ ok=1 ⚠ warn=0 ✖ fail=1 ○ skipped=0"
    muted = brand.PALETTE["muted"]
    styled = {
        shown.plain[span.start : span.end]: str(span.style) for span in shown.spans
    }
    assert styled["⚠ "] == f"bold {muted}"
    assert styled["✖ "] == f"bold {brand.STATUS_COLORS['fail']}"


def test_dashboard_summary_shows_counters_and_problems_as_symbol_plus_text() -> None:
    from dataclasses import replace

    from rich.text import Text

    from harness.console.kernel.home_snapshot import build_home_snapshot
    from harness.console.tui.screens.dashboard import (
        HomeContext,
        _render_summary,
        _snapshot_facts,
    )

    data = replace(
        _fake_dashboard_data(),
        fail=1,
        problems=(
            ("fail", "env.git", "git missing"),
            ("warn", "repo_map.tier", "minimal"),
        ),
        memory_index=CheckResult(
            id="memory.index", group="memory", status="ok", message="индекс готов"
        ),
    )
    plain = Text.from_markup(_render_summary(data)).plain.split("\n")
    assert plain[0] == "health (offline): ✔ ok=5 ⚠ warn=1 ✖ fail=1 ○ skipped=2"
    assert "  ✖ fail env.git — git missing" in plain
    assert "  ⚠ warn repo_map.tier — minimal" in plain
    # A status is also never a colour alone on the cards.
    banner = brand.BannerInfo(
        version="1.0.0", capabilities=(), repo="~/app", branch=None
    )
    cards = {
        card_id: dict(rows)
        for card_id, _title, rows in _snapshot_facts(
            data, build_home_snapshot(data, HomeContext()), banner, "app"
        )
    }
    assert cards["card-harness"]["Дрейф"].plain == "✔ нет"
    assert cards["card-memory"]["Состояние"].plain == "✔ индекс готов"


def test_a_long_path_is_cut_from_the_left_at_a_separator() -> None:
    path = "/home/malove/Projects/Code/claude-agent-harness"
    assert brand.elide_path(path, 80) == path
    assert brand.elide_path(path, 28) == "…/Code/claude-agent-harness"
    assert brand.elide_path(path, 23) == "…/claude-agent-harness"
    assert brand.elide_path(path, 10) == "…t-harness"


def _attention_data() -> DashboardData:
    from dataclasses import replace

    return replace(
        _fake_dashboard_data(),
        fail=2,
        warn=1,
        drift_state="drift",
        problems=(
            ("fail", "files.skill_snapshot", "snapshot differs from 1.4.6"),
            ("fail", "files.integrations", "integrations: tracker token missing"),
            ("warn", "environment.uv", "uv 0.4 is older than 0.5"),
        ),
    )


def _home_context() -> object:
    from harness.console.kernel.repo_map import MapEdge, MapFile, RepoMapView
    from harness.console.kernel.repo_map_settings import MemoryStatus
    from harness.console.tui.screens.dashboard import HomeContext

    view = RepoMapView(
        payload={},
        origin="кэш",
        commit="a" * 40,
        tier="full",
        parser="tree-sitter",
        degradation_reason="",
        estimated_tokens=38400,
        provenance={},
        files=tuple(MapFile(f"f{index}.py", (), "ok") for index in range(412)),
        edges=tuple(
            MapEdge(f"f{index}.py", "f0.py", "import", "high") for index in range(1860)
        ),
        diagnostics=(),
    )
    memory = MemoryStatus(True, True, ("adr", "glossary"), 18, top_k=5, max_tokens=1000)
    return HomeContext(repo_map=view, memory=memory)


def _context_data() -> DashboardData:
    from dataclasses import replace

    return replace(
        _attention_data(),
        repo_map_tier="Repo Map: tier=full (offline parser bundle detected)",
        memory_index=CheckResult(
            id="memory.index",
            group="memory",
            status="ok",
            message="индекс валиден (FTS5)",
        ),
    )


_BANNER = brand.BannerInfo(
    version="1.4.6",
    capabilities=("backend-orchestration",),
    repo="~/Code/claude-agent-harness",
    branch="feature/issue-721-console-design-system",
    installed_version="1.4.6",
    installed_commit="85abd57a",
)


@pytest.mark.parametrize("language", ["ru", "en"])
def test_home_context_cards_show_only_facts_the_console_reads(language: str) -> None:
    from harness.console.kernel.home_snapshot import build_home_snapshot
    from harness.console.tui.screens.dashboard import HomeContext, _snapshot_facts

    data = _context_data()
    cards = _snapshot_facts(
        data,
        build_home_snapshot(data, _home_context()),  # type: ignore[arg-type]
        _BANNER,
        "claude-agent-harness",
        language,
    )
    shown = {
        title: [(label, value.plain) for label, value in rows]
        for _id, title, rows in cards
    }
    assert list(shown) == [
        "Контекст проекта",
        "Harness",
        "Оркестрация",
        "Repo Map",
        "Память проекта",
    ]
    if language == "ru":
        assert shown["Repo Map"] == [
            ("Уровень", "full"),
            ("Актуальность", "✔ карта для HEAD"),
            ("Файлов", "412"),
            ("Связей", "1860"),
            ("Источник", "кэш"),
            ("Объём", "≈38 400 токенов"),
        ]
        assert shown["Память проекта"] == [
            ("Состояние", "✔ индекс валиден (FTS5)"),
            ("Индекс", "18 документов"),
            ("Источники", "adr · glossary"),
            ("Лимит поиска", "5 · 1 000 токенов"),
        ]
        assert shown["Harness"] == [
            ("Установлен", "1.4.6 · 85abd57a"),
            ("Модули", "backend-orchestration"),
            ("Дрейф", "⚠ есть"),
        ]
    else:
        assert [value for _label, value in shown["Repo Map"]] == [
            "full",
            "✔ map for HEAD",
            "412",
            "1860",
            "cache",
            "≈38,400 tokens",
        ]
        assert shown["Память проекта"][1:] == [
            ("Индекс", "18 documents"),
            ("Источники", "adr · glossary"),
            ("Лимит поиска", "5 · 1,000 tokens"),
        ]
    assert shown["Контекст проекта"] == [
        ("Проект", "claude-agent-harness"),
        ("Ветка", "feature/issue-721-console-design-system"),
    ]
    # Without a cached map or a memory policy nothing is invented: unknown facts are a dash.
    bare = {
        title: dict((label, value.plain) for label, value in rows)
        for _id, title, rows in _snapshot_facts(
            _fake_dashboard_data(),
            build_home_snapshot(_fake_dashboard_data(), HomeContext()),
            brand.BannerInfo(version="1", capabilities=(), repo="~/x", branch=None),
            "x",
            language,
        )
    }
    assert bare["Контекст проекта"]["Ветка"] == "—"
    assert bare["Harness"]["Модули"] == "—"
    assert set(bare["Repo Map"]) == {"Уровень", "Актуальность"}
    assert bare["Память проекта"] == {"Состояние": "—"}


def test_the_diagnostics_screen_is_a_console_server_client() -> None:
    """Diagnostics reads its report and applies its fixes through the server client only."""
    import inspect

    from harness.console.tui.screens.diagnostics import DiagnosticsScreen

    parameters = inspect.signature(DiagnosticsScreen).parameters
    assert parameters["client"].default is inspect.Parameter.empty
    assert parameters["client"].kind is inspect.Parameter.KEYWORD_ONLY
    assert not {"collect_diagnostics", "apply_local_fixes"} & set(parameters)
