"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.console.screens.project_setup import ProjectSetupScreen
from harness.console.shell import Fold

from tests.console._home_client import fake_home
from tests.console._pilot_wait import press, wait_until


def test_selecting_another_project_replaces_the_dashboard_context(
    tmp_path: Path,
) -> None:
    second = tmp_path / "backend"
    second.mkdir()
    subprocess.run(["git", "init", "-q", str(second)], check=True)

    async def scenario() -> None:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(120, 48)) as pilot:
            await pilot.press("p")
            await wait_until(pilot, lambda: isinstance(app.screen, ProjectSetupScreen))
            app.screen.query_one("#project-path", Input).value = str(second)
            await press(pilot, "#inspect-project")
            await app.workers.wait_for_complete()
            await pilot.pause()
            await press(pilot, "#activate-project")
            await wait_until(
                pilot,
                lambda: isinstance(app.screen, DashboardScreen)
                and app.screen.query("TopBar"),
            )
            assert isinstance(app.screen, DashboardScreen)
            assert app.repo == second.resolve()
            assert app.screen.repo == second.resolve()

    asyncio.run(scenario())
    assert not (second / ".harness").exists()


def test_install_runs_the_distribution_in_target_and_activates_it(
    tmp_path: Path,
) -> None:
    second = tmp_path / "backend with spaces"
    second.mkdir()
    subprocess.run(["git", "init", "-q", str(second)], check=True)
    seen: list[tuple[list[str], Path | None]] = []

    def runner(
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        seen.append((list(argv), cwd))
        return subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )

    async def scenario() -> None:
        app = HarnessConsoleApp(tmp_path, command_runner=runner)
        async with app.run_test(size=(140, 60)) as pilot:
            await pilot.press("p")
            await wait_until(pilot, lambda: isinstance(app.screen, ProjectSetupScreen))
            app.screen.query_one("#project-path", Input).value = str(second)
            await press(pilot, "#inspect-project")
            await app.workers.wait_for_complete()
            await pilot.pause()
            options = app.screen.query_one("#capability", RadioSet)
            options.query(RadioButton)[-1].value = True
            await pilot.pause()
            await press(pilot, "#install-project")
            await pilot.pause()
            assert seen == []
            # The Harness section's confirmation form: nothing runs until it is accepted.
            await press(pilot, "#cancel")
            await pilot.pause()
            assert seen == []
            await press(pilot, "#install-project")
            await pilot.pause()
            await press(pilot, "#run")
            await app.workers.wait_for_complete()
            await pilot.pause()
            output = str(app.screen.query_one("#setup-output", Static).render())
            assert len(seen) == 1, (seen, output)
            # The flow continues: the project becomes the target only on completion.
            assert isinstance(app.screen, ProjectSetupScreen)
            assert app.repo == tmp_path
            await press(pilot, "#activate-project")
            await wait_until(
                pilot,
                lambda: isinstance(app.screen, DashboardScreen)
                and app.screen.query("TopBar"),
            )
            assert app.repo == second.resolve()
            assert isinstance(app.screen, DashboardScreen)

    asyncio.run(scenario())
    assert len(seen) == 1 and seen[0][1] == second
    assert str(second) in seen[0][0]
    assert (second / ".harness/orchestration/roles").is_dir()
    assert (second / ".harness/project.json").is_file()
    assert not (tmp_path / ".harness").exists()


def test_installed_capability_stays_selected_and_the_flow_shows_its_stages(
    tmp_path: Path,
) -> None:
    import json

    second = tmp_path / "backend"
    (second / ".harness").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(second)], check=True)
    (second / ".harness/harness.lock").write_text(
        json.dumps(
            {"capabilities": ["pvmalove-suite", "backend-orchestration"], "files": {}}
        ),
        encoding="utf-8",
    )

    async def scenario() -> None:
        app = HarnessConsoleApp(tmp_path)
        async with app.run_test(size=(120, 48)) as pilot:
            await pilot.press("p")
            await wait_until(pilot, lambda: isinstance(app.screen, ProjectSetupScreen))
            screen = app.screen
            assert "Выбор проекта" in str(
                screen.query_one("#setup-stage", Static).render()
            )
            screen.query_one("#project-path", Input).value = str(second)
            await press(pilot, "#inspect-project")
            await app.workers.wait_for_complete()
            await pilot.pause()
            pressed = screen.query_one("#capability", RadioSet).pressed_index
            assert screen.options[pressed][0] == "backend-orchestration"  # type: ignore[attr-defined]
            stage = str(screen.query_one("#setup-stage", Static).render())
            assert "▶ Предварительные проверки" in stage
            plan = str(screen.query_one("#installation-plan", Static).render())
            assert "Состав     Backend (backend-orchestration)" in plan
            await press(pilot, "#browse-project")
            await pilot.pause()
            assert len(screen.query("#directory-browser")) == 1

    asyncio.run(scenario())


def test_late_results_of_the_previous_project_do_not_reach_the_new_dashboard(
    tmp_path: Path,
) -> None:
    import threading

    from textual.app import App

    from harness.console.data import DashboardData
    from tests.console.test_console_app import _fake_dashboard_data

    release = threading.Event()
    first, second = tmp_path / "first", tmp_path / "second"

    def slow_first(repo: Path, *, online: bool = False) -> DashboardData:
        release.wait(10)
        return _fake_dashboard_data()

    def marked_second(repo: Path, *, online: bool = False) -> DashboardData:
        return DashboardData(1, 0, 0, 0, "full", "second-project-marker", "clean", None)

    class Host(App[None]):
        def on_mount(self) -> None:
            self.push_screen(
                DashboardScreen(first, home_client=fake_home(slow_first, repo=first))
            )

    async def scenario() -> str:
        app = Host()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.switch_screen(
                DashboardScreen(
                    second, home_client=fake_home(marked_second, repo=second)
                )
            )
            await pilot.pause()
            release.set()
            await pilot.pause(0.5)
            return str(app.screen.query_one("#dashboard-summary", Static).content)

    summary = asyncio.run(scenario())
    assert "second-project-marker" in summary
    assert "9.9.9" not in summary


def test_report_summary_separates_checked_skipped_and_failing_checks() -> None:
    from harness.console.screens.project_setup import ChecksSummary, summarize_report
    from harness.health.model import CheckResult, Fix, Report

    report = Report(
        1,
        "/x",
        False,
        [
            CheckResult("environment.codex_sandbox", "environment", "ok", "ok"),
            CheckResult("tracker.auth", "tracker", "skipped", "офлайн"),
            CheckResult("files.project_json", "files", "fail", "bad", Fix("fix")),
            CheckResult("files.agents_md", "files", "warn", "old"),
        ],
    )
    # A skipped check is not a success: 4 checks, 3 ran, 2 need a fix, 1 was not checked.
    assert summarize_report(report) == ChecksSummary(3, 4, 2, 1)


def test_the_busy_note_has_an_english_text() -> None:
    from harness.console import i18n

    assert (
        i18n.tr("en", "Дождитесь окончания операции")
        == "Wait for the operation to finish"
    )


def test_setup_output_marks_report_statuses_but_not_plain_list_items() -> None:
    from harness.console.screens.diagnostics import styled_log

    text = "- установка\nИтого: ok=1 warn=0 fail=1 skipped=1\n[FAIL] env.uv: нет\n- net: офлайн"
    assert styled_log(text).plain.split("\n") == [
        "- установка",
        "Итого: ✔ ok=1 ⚠ warn=0 ✖ fail=1 ○ skipped=1",
        "✖ [FAIL] env.uv: нет",
        "○ - net: офлайн",
    ]


def test_styled_log_ignores_foreign_lines_that_only_look_like_a_report_total() -> None:
    from harness.console.screens.diagnostics import styled_log

    text = "Итого: 3 файла\n- элемент списка"
    assert styled_log(text).plain == text


def test_open_project_has_no_escape_binding_of_its_own() -> None:
    from textual.binding import Binding

    own = ProjectSetupScreen.__dict__.get("BINDINGS", [])
    keys = [b.key if isinstance(b, Binding) else b[0] for b in own]
    assert "escape" not in keys
    assert not hasattr(ProjectSetupScreen, "action_cancel")


def test_the_screen_shows_no_demo_data_from_the_mockup() -> None:
    """The mockup's sample values (branch, counts, paths, version) are not in the sources: the
    screen shows only what the console receives."""
    root = Path(__file__).resolve().parents[2] / "harness" / "console"
    for source in (root / "screens" / "project_setup.py", root / "project_target.py"):
        text = source.read_text(encoding="utf-8")
        for demo in (
            "feature/issue-721",
            "16 из 27",
            "11 онлайн",
            "/home/malove",
            "1.4.6",
        ):
            assert demo not in text, f"{source.name}: {demo}"


def test_an_option_button_keeps_both_lines_of_its_label() -> None:
    """Guards the private Textual API `_OptionButton` relies on (`_make_label`, `_label`)."""
    from textual.geometry import Size

    from harness.console.screens.project_setup import _OptionButton

    button = _OptionButton("name\ndescription")
    assert button._label.plain == "name\ndescription"
    assert button.get_content_height(Size(40, 10), Size(80, 24), 40) == 2
