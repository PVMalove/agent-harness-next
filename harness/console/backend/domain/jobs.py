"""A console job: its phase, its bounded output read by cursor, the refusals of a job request,
the cleanup plan digest a deletion needs and the masked record the command journal keeps."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, NamedTuple

from harness.configuration import SECRET_MASK, mask_secrets

from ...kernel.catalog import CONFIRMATION_REASONS, REVERSIBILITY_LABELS, CatalogEntry

_FRAGMENT_CHARS = 4096
# A character takes at most six bytes in an encoded reply (a control character as `\u00XX`),
# so a batch stays well below the server's 64 KiB message limit.
_BATCH_CHARS = 8192
_BATCH_EVENTS = 8
_OUTPUT_LIMIT_CHARS = 4 * 1024 * 1024
# The TUI deletes only the cleanup set its preview approved (`--plan-digest`); a job demands the same.
_PLAN_COMMANDS = frozenset({"cleanup-apply", "cleanup-hard-apply"})
_PLAN_DIGEST = re.compile(r"[0-9a-f]{64}")

Phase = Literal["running", "completed", "failed", "cancelled"]
# The console sections whose catalog commands a client lists with `job.catalog`.
COMMAND_SECTIONS = (
    "harness",
    "diagnostics",
    "repo-map",
    "setup",
    "configuration",
    "memory",
)


class JobRejected(Exception):
    """A job request refused after its envelope was read; without a message the protocol uses
    the code's own."""

    def __init__(
        self, code: str, message: str | None = None, *, job_id: str | None = None
    ) -> None:
        super().__init__(code)
        self.code, self.message = code, message
        self.job_id = job_id


class Fragment(NamedTuple):
    channel: str
    text: str


@dataclass
class Job:
    id: str
    command_id: str
    # The job holds the server's one mutation slot until it ends.
    mutating: bool = False
    output: list[Fragment] = field(default_factory=list)
    output_chars: int = 0
    truncated: bool = False
    phase: Phase = "running"
    returncode: int | None = None
    error: str = ""
    # Replaced on every change, so a reader waits on the event it saw before it read.
    next_change: asyncio.Event = field(default_factory=asyncio.Event)

    def append(self, channel: str, text: str) -> None:
        """Store output in bounded fragments until the limit, then only mark the cut."""
        for offset in range(0, len(text), _FRAGMENT_CHARS):
            part = text[offset : offset + _FRAGMENT_CHARS]
            if self.truncated or self.output_chars + len(part) > _OUTPUT_LIMIT_CHARS:
                self.truncated = True
                break
            self.output.append(Fragment(channel, part))
            self.output_chars += len(part)
        if text:
            self.notify()

    def notify(self) -> None:
        previous, self.next_change = self.next_change, asyncio.Event()
        previous.set()

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "command_id": self.command_id,
            "mutating": self.mutating,
            "phase": self.phase,
            "cursor": len(self.output),
            "done": self.phase != "running",
            "truncated": self.truncated,
            "returncode": self.returncode,
            "error": self.error,
        }

    def snapshot(self, cursor: object) -> dict[str, object]:
        """The summary with the next bounded batch after `cursor`; done once replay caught up."""
        if type(cursor) is not int or not 0 <= cursor <= len(self.output):
            raise JobRejected("invalid_cursor")
        batch: list[dict[str, str]] = []
        size = 0
        for fragment in self.output[cursor : cursor + _BATCH_EVENTS]:
            if size + len(fragment.text) > _BATCH_CHARS:
                break
            batch.append(fragment._asdict())
            size += len(fragment.text)
        next_cursor = cursor + len(batch)
        return {
            **self.summary(),
            "output": batch,
            "cursor": next_cursor,
            "done": self.phase != "running" and next_cursor == len(self.output),
        }


def describe_command(
    entry: CatalogEntry, *, section: str, available: bool
) -> dict[str, object]:
    """What a client shows of a catalog command and what its start must carry: the class with its
    label, the confirmation with its reason, the typed word, the input fields and whether a
    cleanup plan digest is needed. The texts are the catalog's Russian source strings."""
    return {
        "command_id": entry.key,
        "title": entry.title,
        "section": section,
        "reversibility": entry.reversibility.value,
        "reversibility_label": REVERSIBILITY_LABELS[entry.reversibility],
        "needs_confirmation": entry.needs_confirmation,
        "confirmation_reason": CONFIRMATION_REASONS.get(entry.reversibility),
        "typed_confirmation": entry.typed_confirmation,
        "read_only": entry.read_only,
        "inputs": list(entry.inputs),
        "plan_required": entry.key in _PLAN_COMMANDS,
        "available": available,
    }


def plan_digest(command_id: str, body: Mapping[str, object]) -> str | None:
    """The cleanup plan digest a deletion command must carry, and only such a command may."""
    digest = body.get("plan_digest")
    if command_id not in _PLAN_COMMANDS and "plan_digest" in body:
        raise JobRejected("bad_request")
    if command_id in _PLAN_COMMANDS and not (
        isinstance(digest, str) and _PLAN_DIGEST.fullmatch(digest)
    ):
        raise JobRejected("plan_required")
    return digest if isinstance(digest, str) else None


def journal_record(
    timestamp: str,
    client: str,
    argv: list[str],
    reversibility: str,
    returncode: int | None,
    command_id: str,
) -> dict[str, object]:
    """The command journal entry of a finished job, with every secret argument masked."""
    masked: list[object] = []
    secret_next = False
    for arg in argv:
        key, separator, value = arg.partition("=")
        secret_key = key.lstrip("-")
        if secret_next:
            masked.append(SECRET_MASK)
            secret_next = False
        elif separator and mask_secrets(value, secret_key) == SECRET_MASK:
            masked.append(key + "=" + SECRET_MASK)
        elif arg.startswith("-") and mask_secrets("value", secret_key) == SECRET_MASK:
            masked.append(arg)
            secret_next = True
        else:
            masked.append(mask_secrets(arg))
    return {
        "timestamp": timestamp,
        "client": client,
        "command_id": command_id,
        "argv": masked,
        "reversibility": reversibility,
        "returncode": returncode,
    }
