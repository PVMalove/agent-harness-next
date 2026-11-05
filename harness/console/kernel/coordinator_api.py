"""Thin structured client over the coordinator CLI and `harness cleanup` for the container route and
the recovery screen. It adds no lifecycle, approval, QA or cleanup rule: every state comes from the
JSON documents the same CLI prints for any operator. The client

* builds argv from the introspected argparse tree of the coordinator (a renamed flag fails here,
  not on a screen), for an explicit allowlist of subcommands only;
* runs it through an injected `CommandRunner` (`capturing_runner` closes stdin), never through the
  container engine and never through a protocol of the runtime;
* types the answer: a document, a refusal (a document plus a non-zero exit), a failure (a non-zero
  exit without a document; stderr is kept as opaque text, never parsed), an unparsed success or an
  unavailable process.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

from harness.orchestration import coordinator

from .coordinator_catalog import (
    CoordinatorCommand,
    CoordinatorField,
    _fields,
    process_argv,
    subparser,
)
from .catalog import Reversibility
from .runner import CommandRunner, capturing_runner

# The only coordinator subcommands the console reaches. Anything else (send, abandon, decide, ...)
# keeps its own explicit form; none of them touches a container engine from here.
ALLOWED_PATHS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("batch", "list"),
        ("dispatch", "preflight"),
        ("dispatch", "propose"),
        ("dispatch", "create"),
        ("dispatch", "status"),
        ("qa", "run"),
        ("qa", "status"),
        ("recovery", "status"),
        ("recovery", "reload"),
        ("recovery", "resume"),
        ("recovery", "fix"),
        ("recovery", "abort"),
    }
)

# A flag or a value that would weaken the native approval, the containerization boundary or an
# agent's permission model is never built, whatever a screen passes.
FORBIDDEN_FRAGMENTS = (
    "--docker",
    "auto-approve",
    "auto_approve",
    "--yes",
    "--force",
    "dangerously",
    "skip-permissions",
    "permission-mode",
    "bypass",
    "--confirm",
)


class Outcome(str, Enum):
    DOCUMENT = "document"
    REFUSED = "refused"
    FAILED = "failed"
    UNPARSED = "unparsed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ApiResult:
    """One command's typed answer. `documents` are the JSON objects of stdout in order; `stderr`
    and `stdout_text` stay opaque text for display and are never a contract."""

    outcome: Outcome
    argv: tuple[str, ...]
    documents: tuple[dict[str, object], ...] = ()
    returncode: int | None = None
    stderr: str = ""
    stdout_text: str = ""

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.DOCUMENT

    @property
    def document(self) -> dict[str, object] | None:
        """The first document, for a command that prints one."""
        return self.documents[0] if self.documents else None

    def section(self, key: str) -> object | None:
        """The value of `key` in the first document that has it (`plan`/`result` of cleanup)."""
        for document in self.documents:
            if key in document:
                return document[key]
        return None

    @property
    def problem_text(self) -> str:
        """What went wrong, verbatim: the process error or stderr, else the raw output."""
        return (self.stderr or self.stdout_text).strip()


class ArgvError(ValueError):
    """A command the client refuses to build; nothing runs."""


def parse_documents(text: str) -> tuple[tuple[dict[str, object], ...], bool]:
    """Every JSON object printed back to back; the flag is False when anything else is present."""
    decoder = json.JSONDecoder()
    documents: list[dict[str, object]] = []
    index, length = 0, len(text)
    while index < length:
        if text[index].isspace():
            index += 1
            continue
        try:
            value, index = decoder.raw_decode(text, index)
        except ValueError:
            return tuple(documents), False
        if not isinstance(value, dict):
            return tuple(documents), False
        documents.append(value)
    return tuple(documents), bool(documents)


def _fields_of(path: tuple[str, ...]) -> dict[str, CoordinatorField]:
    if path not in ALLOWED_PATHS:
        raise ArgvError(f"coordinator command {' '.join(path)!r} is not reachable here")
    return {
        field.dest: field for field in _fields(subparser(coordinator.parser(), path))
    }


def forbidden_in(argv: Sequence[str]) -> str | None:
    """The first token that carries a forbidden flag or value, else None."""
    for token in argv:
        lowered = token.lower()
        for fragment in FORBIDDEN_FRAGMENTS:
            if lowered.startswith("--") and fragment in lowered:
                return token
            if lowered == fragment:
                return token
    return None


def coordinator_argv(
    repo: Path, path: tuple[str, ...], values: Mapping[str, str | Sequence[str] | bool]
) -> list[str]:
    """Process argv of `coordinator <path> ...`: values are keyed by the argparse `dest`; an
    unknown dest, a missing required one or a value outside `choices` refuses the build."""
    fields = _fields_of(path)
    unknown = sorted(set(values) - set(fields))
    if unknown:
        raise ArgvError(f"{' '.join(path)} has no argument {', '.join(unknown)}")
    flat: dict[str, str] = {}
    for dest, raw in values.items():
        field = fields[dest]
        if isinstance(raw, bool):
            flat[dest] = "1" if raw else ""
        elif isinstance(raw, str):
            flat[dest] = raw
        else:
            flat[dest] = "\n".join(raw)
        text = flat[dest].strip()
        if text and field.takes_value and field.choices and not field.repeatable:
            if text not in field.choices:
                raise ArgvError(f"{field.flag}: {text!r} is not one of {field.choices}")
    for dest, field in fields.items():
        if field.required and not flat.get(dest, "").strip():
            raise ArgvError(f"{' '.join(path)} requires {field.flag}")
    command = CoordinatorCommand(
        key="-".join(path),
        title=" ".join(path),
        group=path[0],
        path=path,
        reversibility=Reversibility.REVERSIBLE,
        fields=tuple(fields.values()),
    )
    argv = process_argv(command.cli_argv(repo, flat))
    bad = forbidden_in(argv)
    if bad is not None:
        raise ArgvError(f"forbidden argument refused: {bad}")
    return argv


def cleanup_argv(repo: Path, *, apply_digest: str | None = None) -> list[str]:
    """`harness cleanup <repo> --mode soft`, with `--apply --plan-digest <digest>` bound to one
    previewed plan. The mode is always soft and `--confirm` is never passed."""
    argv = ["harness", "cleanup", str(repo), "--mode", "soft"]
    if apply_digest is not None:
        digest = apply_digest.strip()
        if not digest:
            raise ArgvError("apply requires the digest of the previewed plan")
        argv += ["--apply", "--plan-digest", digest]
    return process_argv(argv)


class CoordinatorApi:
    """Runs the allowed commands of one repository through an injected runner."""

    def __init__(self, repo: Path, runner: CommandRunner = capturing_runner) -> None:
        self.repo = repo
        self._runner = runner

    def call(
        self,
        path: tuple[str, ...],
        values: Mapping[str, str | Sequence[str] | bool] | None = None,
    ) -> ApiResult:
        return self._run(coordinator_argv(self.repo, path, values or {}))

    def cleanup(self, *, apply_digest: str | None = None) -> ApiResult:
        return self._run(cleanup_argv(self.repo, apply_digest=apply_digest))

    def _run(self, argv: list[str]) -> ApiResult:
        frozen = tuple(argv)
        try:
            completed = self._runner(argv, cwd=self.repo)
        except (
            Exception
        ) as exc:  # the process boundary: any failure is shown, none is hidden
            return ApiResult(Outcome.UNAVAILABLE, frozen, stderr=str(exc) or repr(exc))
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        documents, clean = parse_documents(stdout)
        code = completed.returncode
        if code == 0:
            outcome = Outcome.DOCUMENT if clean else Outcome.UNPARSED
        else:
            outcome = Outcome.REFUSED if clean else Outcome.FAILED
        return ApiResult(
            outcome,
            frozen,
            documents if clean or outcome is Outcome.UNPARSED else (),
            code,
            stderr,
            stdout if not clean else "",
        )
