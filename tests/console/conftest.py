"""Console tests exercise units with fake process and application boundaries."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def unit_boundaries(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    if request.node.get_closest_marker("real_process"):
        yield
        return
    attempted: list[str] = []

    def forbidden_process(*args: object, **kwargs: object) -> None:
        attempted.append("subprocess")
        raise AssertionError("Console unit tests must inject a process runner")

    def forbidden_ui(*args: object, **kwargs: object) -> None:
        attempted.append("App.run_test")
        raise AssertionError("Console tests must not start an application")

    monkeypatch.setattr(subprocess, "Popen", forbidden_process)
    try:
        from textual.app import App
    except ImportError:
        pass  # Stdlib-only units remain runnable without the optional TUI package.
    else:
        monkeypatch.setattr(App, "run_test", forbidden_ui)
    yield
    assert not attempted, f"Console unit test crossed an external boundary: {attempted}"


@pytest.fixture(autouse=True)
def private_clipboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never access the developer's real clipboard."""
    monkeypatch.setenv("HARNESS_CONSOLE_SYSTEM_CLIPBOARD", "0")
