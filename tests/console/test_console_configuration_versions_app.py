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


def test_a_restore_is_the_gateway_job_with_the_digests_of_the_shown_files(
    tmp_path: Path,
) -> None:
    from harness.console.kernel.configuration_snapshot import config_digest
    from harness.console.tui.client import JobResult
    from harness.console.tui.configuration_gateway import ServerConfiguration
    from harness.console.tui.screens.configuration_versions import (
        ConfigurationVersionsScreen,
    )

    from ._home_client import FakeHomeClient

    raw = installed_project(tmp_path)
    client = FakeHomeClient(tmp_path)
    client.job_result = JobResult("completed", 0, "Версия восстановлена.\n", "", False, None)
    screen = ConfigurationVersionsScreen(tmp_path, ServerConfiguration(client))

    message = screen._restore("v-1", {"project.json": raw, "orchestration.json": None})

    assert message == "Версия восстановлена."
    assert client.screen_requests == [
        (
            "job",
            "configuration-restore",
            {
                "request": (
                    '{"version":"v-1","expected":{"project.json":"'
                    + config_digest(raw)
                    + '","orchestration.json":""}}'
                )
            },
            True,
        )
    ]
