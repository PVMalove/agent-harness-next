"""The coordinator commands of the Recovery and Container route screens through the console
server. Reads come from the screen snapshots (`batch list` from `recovery.snapshot`, `recovery
status`, `dispatch preflight`), recovery actions run as server jobs under its confirmation rules,
and nothing here starts a process: a path the server does not serve goes to the `fallback`
client, or is refused when there is none."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from ..kernel.coordinator_api import (
    ApiResult,
    ArgvError,
    CoordinatorApi,
    Outcome,
    classify,
)
from ..kernel.coordinator_catalog import COORDINATOR_COMMANDS
from .client import ConsoleClientError, ScreenClient

Values = Mapping[str, str | Sequence[str] | bool]

_COMMANDS = {command.key: command for command in COORDINATOR_COMMANDS}

# The recovery actions and the server job that runs each; `recovery fix` with `apply` is the
# separate, confirmed `recovery-fix-apply` entry.
_JOBS: dict[tuple[str, ...], str] = {
    ("recovery", "reload"): "recovery-reload",
    ("recovery", "resume"): "recovery-resume",
    ("recovery", "abort"): "recovery-abort",
    ("recovery", "fix"): "recovery-fix",
}
_ROUTE_VALUES = frozenset({"batch", "role", "runtime"})


def _flat(values: Values) -> dict[str, str]:
    """Job values as `coordinator_argv` flattens them: a flag is `1` or empty, a list is one
    line per item."""
    flat: dict[str, str] = {}
    for dest, raw in values.items():
        if isinstance(raw, bool):
            flat[dest] = "1" if raw else ""
        elif isinstance(raw, str):
            flat[dest] = raw
        else:
            flat[dest] = "\n".join(raw)
    return flat


def _lines(raw: str | Sequence[str] | bool) -> list[str]:
    if isinstance(raw, bool):
        return []
    return [raw] if isinstance(raw, str) else list(raw)


def _text(values: Values, name: str, default: str = "") -> str:
    raw = values.get(name, default)
    return raw if isinstance(raw, str) else default


class ServerCoordinatorApi:
    """`CoordinatorApi.call` and `cleanup` over the console server client."""

    def __init__(
        self,
        repo: Path,
        client: ScreenClient,
        *,
        fallback: CoordinatorApi | None = None,
    ) -> None:
        self.repo = repo
        self._client = client
        self._fallback = fallback

    def call(
        self,
        path: tuple[str, ...],
        values: Values | None = None,
        *,
        confirmed: bool = False,
    ) -> ApiResult:
        """The answer of `path` with `values`; a client failure or a refused job is an
        `UNAVAILABLE` result, never an exception. `confirmed` reaches only a server job."""
        given = dict(values or {})
        if path in _JOBS:
            return self._job(path, given, confirmed)
        try:
            if path == ("batch", "list") and not given:
                return self._batches()
            if path == ("recovery", "status"):
                status = self._client.recovery(
                    _text(given, "batch"), _lines(given.get("skip", ()))
                ).status
                if status is not None:
                    return status
            elif path == ("dispatch", "preflight") and set(given) <= _ROUTE_VALUES:
                preflight = self._client.container_route(
                    _text(given, "batch"),
                    _text(given, "role", "developer"),
                    _text(given, "runtime"),
                ).preflight
                if preflight is not None:
                    return preflight
        except ConsoleClientError as exc:
            return ApiResult(Outcome.UNAVAILABLE, path, stderr=str(exc))
        if self._fallback is None:
            raise ArgvError(
                f"coordinator command {' '.join(path)!r} is not served by the console server"
            )
        return self._fallback.call(path, given)

    def cleanup(self, *, apply_digest: str | None = None) -> ApiResult:
        """`harness cleanup` is not a server job: only the fallback client runs it."""
        if self._fallback is None:
            raise ArgvError("cleanup is not served by the console server")
        return self._fallback.cleanup(apply_digest=apply_digest)

    def _batches(self) -> ApiResult:
        history = self._client.recovery().history
        if history.unavailable:
            return ApiResult(
                Outcome.UNAVAILABLE, ("batch", "list"), stderr=history.unavailable
            )
        return ApiResult(
            Outcome.DOCUMENT,
            ("batch", "list"),
            ({"batches": [asdict(batch) for batch in history.batches]},),
            0,
        )

    def _job(
        self, path: tuple[str, ...], values: dict[str, str | Sequence[str] | bool], confirmed: bool
    ) -> ApiResult:
        key = _JOBS[path]
        if path == ("recovery", "fix") and values.pop("apply", False):
            key = "recovery-fix-apply"
        flat = _flat(values)
        command = _COMMANDS[key]
        argv = tuple(command.cli_argv(self.repo, flat))
        try:
            result = self._client.run_job(key, flat, confirmed=confirmed)
        except ConsoleClientError as exc:
            return ApiResult(Outcome.UNAVAILABLE, argv, stderr=str(exc))
        if result.returncode is None:
            return ApiResult(
                Outcome.UNAVAILABLE,
                argv,
                stderr=result.error or result.stderr or result.phase,
            )
        return classify(argv, result.returncode, result.stdout, result.stderr)
