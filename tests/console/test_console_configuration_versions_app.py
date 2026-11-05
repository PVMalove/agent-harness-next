"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

from pathlib import Path

from harness.configuration_store import ConfigurationStore
from tests.console._configuration_fixture import installed_project


def test_the_save_messages_name_the_storage(tmp_path: Path) -> None:
    from harness.console.tui.screens.configuration import ConfigurationScreen

    installed_project(tmp_path)
    screen = ConfigurationScreen(tmp_path)
    message = screen._save_current("Русский")
    assert message.startswith("Текущая конфигурация сохранена как версия: ")
    assert f"Хранилище: {ConfigurationStore(tmp_path).root}" in message
