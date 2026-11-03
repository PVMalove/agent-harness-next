"""SVG snapshots of the home screen: one pair (160x52 and 80x24) of the Home screen in Russian, with
the dashboard facts, the banner, the project context, the working sessions and the clock fixed and
injected. The pair is the baseline that keeps Home visually unchanged; see
tests/console/_svg_snapshot.py to regenerate it."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest
from textual.screen import Screen

from harness.console import reports
from harness.console.screens.dashboard import DashboardScreen
from tests.console._home_client import fake_home
from tests.console._svg_snapshot import (
    PROJECT,
    SIZES,
    Case,
    capture,
    check_snapshot,
    snapshot_path,
)
from tests.console.test_console_home import BANNER, CONTEXT, DATA, NOW, STAGES

SOURCE = "home"
DIRECTORY = "home"
# A fixed path that does not exist: the path line shows it, so it must not depend on the test run.
REPO = Path("/work") / PROJECT


def _screen(repo: Path) -> Screen[object]:
    return cast(
        Screen[object],
        DashboardScreen(
            repo,
            home_client=fake_home(
                lambda _repo, *, online=False: DATA, lambda _repo: CONTEXT, repo=repo
            ),
            collect_banner=lambda _repo: BANNER,
            now=lambda: NOW,
        ),
    )


CASES = (Case(name="home", sections=("Главная",), state="", make_screen=_screen),)


@pytest.mark.parametrize("size", SIZES, ids=[f"{w}x{h}" for w, h in SIZES])
@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
def test_home_matches_its_snapshot(
    case: Case, size: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        reports, "load_ledger_view", lambda _repo: reports.LedgerView(stages=STAGES)
    )
    svg = asyncio.run(capture(case, size, REPO, source=SOURCE))
    check_snapshot(snapshot_path(DIRECTORY, case, size), svg)
