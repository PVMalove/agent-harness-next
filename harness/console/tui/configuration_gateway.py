"""Where «Настройка» reads and writes the configuration. `ServerConfiguration` reads the
`configuration.snapshot` of the project the console server serves and runs every write as its
server job, confirmed by the job's reversibility class (the screen asked the operator first);
`LocalConfiguration` runs the same `configuration_writes` functions in process for a project the
server does not serve (configured from «Открыть проект»). Both refuse a stale file with
`StaleConfiguration` and any other failure with `ValueError`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from harness.configuration_store import StaleConfiguration

from ..kernel import configuration_writes
from ..kernel.catalog import CONFIGURATION_COMMANDS
from ..kernel.configuration import ConfigurationDraft
from ..kernel.configuration_snapshot import ConfigurationFacts, collect_configuration
from .client import ConsoleClientError, ScreenClient, job_start_fits

# The configuration CLI's exit code of a stale file (`configuration_cli.STALE_EXIT`).
STALE_EXIT = 3
TOO_LARGE = (
    "Слишком много изменений для одного запроса к серверу консоли: "
    "примените изменения частями"
)
_ENTRIES = {entry.key: entry for entry in CONFIGURATION_COMMANDS}


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ConfigurationGateway(Protocol):
    def snapshot(self, *, force: bool = False) -> ConfigurationFacts: ...

    def save_draft(self, draft: ConfigurationDraft, description: str) -> str: ...

    def save_current(self, description: str) -> str: ...

    def apply(self, draft: ConfigurationDraft) -> str: ...

    def apply_adapters(self, fingerprint: str) -> str: ...

    def recover(self) -> str: ...

    def restore(self, version: str, expected: dict[str, str]) -> str: ...


class ServerConfiguration:
    """The configuration of the served project through the console server."""

    def __init__(self, client: ScreenClient) -> None:
        self._client = client

    def _run(self, key: str, request: str | None = None) -> str:
        entry = _ENTRIES[f"configuration-{key}"]
        values = {} if request is None else {"request": request}
        if not job_start_fits(entry.key, values, confirmed=entry.needs_confirmation):
            raise ValueError(TOO_LARGE)
        try:
            result = self._client.run_job(
                entry.key, values, confirmed=entry.needs_confirmation
            )
        except ConsoleClientError as exc:
            raise ValueError(str(exc)) from None
        reason = (result.stderr or result.error or result.phase).strip()
        if result.returncode == STALE_EXIT:
            raise StaleConfiguration(reason)
        if result.returncode != 0:
            raise ValueError(reason or result.phase)
        return result.stdout.strip()

    def snapshot(self, *, force: bool = False) -> ConfigurationFacts:
        try:
            return self._client.configuration(force=force)
        except ConsoleClientError as exc:
            raise ValueError(str(exc)) from None

    def save_draft(self, draft: ConfigurationDraft, description: str) -> str:
        return self._run("save-draft", configuration_writes.draft_request(draft, description))

    def save_current(self, description: str) -> str:
        return self._run("save-current", _compact({"description": description}))

    def apply(self, draft: ConfigurationDraft) -> str:
        return self._run("apply", configuration_writes.draft_request(draft))

    def apply_adapters(self, fingerprint: str) -> str:
        return self._run("adapters", _compact({"fingerprint": fingerprint}))

    def recover(self) -> str:
        return self._run("recover")

    def restore(self, version: str, expected: dict[str, str]) -> str:
        return self._run("restore", _compact({"version": version, "expected": expected}))


class LocalConfiguration:
    """The configuration of a project the console server does not serve, written in process."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo

    def snapshot(self, *, force: bool = False) -> ConfigurationFacts:
        return collect_configuration(self.repo)

    def save_draft(self, draft: ConfigurationDraft, description: str) -> str:
        return configuration_writes.save_draft(
            self.repo, configuration_writes.draft_request(draft, description)
        )

    def save_current(self, description: str) -> str:
        return configuration_writes.save_current(
            self.repo, _compact({"description": description})
        )

    def apply(self, draft: ConfigurationDraft) -> str:
        return configuration_writes.apply(
            self.repo, configuration_writes.draft_request(draft)
        )

    def apply_adapters(self, fingerprint: str) -> str:
        return configuration_writes.apply_adapters(
            self.repo, _compact({"fingerprint": fingerprint})
        )

    def recover(self) -> str:
        return configuration_writes.recover(self.repo)

    def restore(self, version: str, expected: dict[str, str]) -> str:
        return configuration_writes.restore(
            self.repo, _compact({"version": version, "expected": expected})
        )
