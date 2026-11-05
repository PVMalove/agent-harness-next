"""Console tests never probe the real Codex/Claude CLIs unless a test opts in."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """An empty Git repository for the console server tests."""
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


@pytest.fixture(autouse=True)
def offline_advisor_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from harness.console.tui.screens import configuration

    monkeypatch.setattr(
        configuration, "availability", lambda provider, cancel: "Готов к запросу (тест)"
    )


@pytest.fixture(autouse=True)
def private_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """A test never reads or overwrites the developer's real clipboard."""
    monkeypatch.setenv("HARNESS_CONSOLE_SYSTEM_CLIPBOARD", "0")


@pytest.fixture(autouse=True)
def offline_home_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ordinary Pilot tests never read the user's tracker."""
    from harness.console.tui import task_titles

    monkeypatch.setattr(task_titles, "load_task_titles", lambda repo, tickets: {})


@pytest.fixture(autouse=True)
def fake_console_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The app connects to a fake console server that answers from the real collect seams of
    the project it is asked about: no test opens a socket or starts a server."""
    from harness.console import launcher
    from tests.console._home_client import FakeHomeClient

    monkeypatch.setattr(launcher, "connect_console", FakeHomeClient)
    monkeypatch.setattr(launcher, "discover_console", FakeHomeClient)
