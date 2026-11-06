"""Server-owned catalog commands: job admission, execution and the readers of a job's output.

Human decisions are ordinary commands with the same confirmation, slot and journal: coordinator
decisions (``batch-approve``, ``batch-decide``, ``batch-attention-resolve``, ``dispatch-propose``
then ``dispatch-create``) and native permission answers (``native-permission-allow`` or
``native-permission-deny``). The coordinator and the runtime recheck every decision.

Completed, failed and cancelled jobs append a record to the command journal. A missing exit code
is null. All user-supplied values are masked, including non-secret values and the cleanup plan
digest. The catalog command id and flags remain available to identify the operation.

A project runs one mutating job at a time. A start refused for it is ``busy`` with the running
job's ``job_id``; ``busy`` without ``job_id`` means the running-job limit. Reads start beside a
mutation. A cancel stops the command and its descendants: the job ends ``cancelled``, or with its
own exit code when the command ended before the stop reached it. Jobs live until server exit,
except that only the newest finished ones are kept.
"""

from __future__ import annotations

import asyncio
import subprocess
import threading
from collections.abc import AsyncGenerator, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

from harness.configuration import SECRET_MASK

from ...kernel.catalog import CatalogEntry, process_argv
from ...kernel.coordinator_catalog import CoordinatorCommand
from ...kernel.process_tree import CommandCancelled
from ...kernel.protocol import MAX_ID_CHARS
from ..domain.approvals import cancel_confirmation_message, start_confirmed
from ..domain.clients import CLIENT_KINDS
from ..domain.jobs import (
    COMMAND_SECTIONS,
    Job,
    JobRejected,
    describe_command,
    journal_record,
    plan_digest,
)
from .ports import CommandJournal, CommandSpec, IdSource, JobExecutor, WallClock

_KEPT_FINISHED = 32
# Each running job holds an event-loop worker thread; snapshot rebuilds need one as well.
_RUNNING_LIMIT = 4
# A stopped command ends within the runner's grace period. A descendant that left the command's
# process group can keep the output open longer; a cancel then answers with the job running.
_CANCEL_WAIT_SECONDS = 5.0


@dataclass
class _Execution:
    """A job with what runs it: the task and the event that asks it to stop."""

    job: Job
    cancel_event: threading.Event = field(default_factory=threading.Event)
    task: asyncio.Task[None] | None = None


class JobService:
    """One server's job admission, command execution, bounded output and independent readers.

    The mutation slot belongs to this server instance. ``ConsoleServer`` acquires the project's
    ``Discovery`` lock before exposing a ``JobService``, so every client of a project shares one
    slot. Processes outside the server (the CLI, a coordinator run directly) are serialized by the
    ledger lock that ``ledger_lock.py`` reports. ``ledger-lock-status`` stays a read beside a
    running mutation, while ``ledger-release-lock`` is ``busy`` like any other mutation: the slot
    holder may own the lock, and a live owner is never released.
    """

    def __init__(
        self,
        repo: Path,
        *,
        catalog: Mapping[str, CommandSpec],
        executor: JobExecutor,
        journal: CommandJournal,
        new_id: IdSource,
        now: WallClock,
        sections: Mapping[str, str] | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self._catalog = catalog
        # The console section that lists a command; a command without one is started only by
        # its own flow (decisions, native permission answers, the selected seed update).
        self._sections = {} if sections is None else dict(sections)
        self._executor = executor
        self._journal = journal
        self._new_id = new_id
        self._now = now
        self._jobs: dict[str, _Execution] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._active_mutation: Job | None = None

    @property
    def active_count(self) -> int:
        return sum(run.job.phase == "running" for run in self._jobs.values())

    def jobs(self) -> list[dict[str, object]]:
        """The summaries of the jobs this server keeps."""
        return [run.job.summary() for run in self._jobs.values()]

    def commands(self, section: object) -> list[dict[str, object]]:
        """The descriptions of a section's kernel catalog commands, with their availability in
        the served project; an unknown section is a bad request."""
        if section not in COMMAND_SECTIONS:
            raise JobRejected("bad_request")
        commands: list[dict[str, object]] = []
        for key, entry in self._catalog.items():
            if self._sections.get(key) != section:
                continue
            description = describe_command(
                entry, section=str(section), available=entry.available(self.repo)
            )
            if isinstance(entry, CoordinatorCommand):
                description["fields"] = [asdict(field) for field in entry.fields]
            commands.append(description)
        return commands

    def start(self, body: Mapping[str, object]) -> Job:
        client = body.get("client", "unknown")
        if client not in CLIENT_KINDS:
            raise JobRejected("bad_request")
        command_id = body.get("command_id")
        if not isinstance(command_id, str):
            raise JobRejected("bad_request")
        entry = self._catalog.get(command_id)
        if entry is None:
            raise JobRejected("unknown_command")
        values = body.get("values", {})
        if not isinstance(values, dict) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in values.items()
        ):
            raise JobRejected("bad_request")
        filled = cast(dict[str, str], values)
        confirmed = body.get("confirmed", False)
        if not entry.accepts(filled) or not isinstance(confirmed, bool):
            raise JobRejected("bad_request")
        typed, dev_environment = (
            (entry.typed_confirmation, entry.dev_environment)
            if isinstance(entry, CatalogEntry)
            else (None, False)
        )
        if not start_confirmed(
            needs_confirmation=entry.needs_confirmation,
            typed_confirmation=typed,
            confirmed=confirmed,
            confirmation=body.get("confirmation"),
        ):
            raise JobRejected("confirmation_required")
        digest = plan_digest(command_id, body)
        try:
            available = entry.available(self.repo)
            argv = process_argv(
                entry.cli_argv(self.repo, filled),
                self.repo,
                dev_environment=dev_environment,
            )
            # Render the journal command from masked inputs. Matching against the finished argv
            # can either leak transformed values or hide unrelated tokens with the same value.
            journal_values = {
                name: SECRET_MASK if value.strip() else ""
                for name, value in filled.items()
            }
            if isinstance(entry, CoordinatorCommand):
                for field in entry.fields:
                    if field.repeatable and field.dest in filled:
                        journal_values[field.dest] = "\n".join(
                            SECRET_MASK
                            for line in filled[field.dest].splitlines()
                            if line.strip()
                        )
            journal_argv = process_argv(
                entry.cli_argv(self.repo, journal_values),
                self.repo,
                dev_environment=dev_environment,
            )
        except Exception as exc:
            raise JobRejected("start_failed", type(exc).__name__) from None
        if not available:
            raise JobRejected("unavailable_command")
        mutating = not entry.read_only
        # The slot is released in the same step that ends its job, so a holder is still running.
        active = self._active_mutation
        if mutating and active is not None:
            raise JobRejected(
                "busy", f"Busy: {active.id} ({active.command_id})", job_id=active.id
            )
        if self.active_count >= _RUNNING_LIMIT:
            raise JobRejected("busy")
        if digest is not None:
            argv += ["--plan-digest", digest]
            journal_argv += ["--plan-digest", SECRET_MASK]
        run = _Execution(Job(self._new_id(), command_id, mutating=mutating))
        job = run.job
        self._jobs[job.id] = run
        task = asyncio.create_task(
            self._execute(
                run, argv, str(client), entry.reversibility.value, journal_argv
            )
        )
        run.task = task
        if mutating:
            self._active_mutation = job
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _execute(
        self,
        run: _Execution,
        argv: list[str],
        client: str,
        reversibility: str,
        journal_argv: list[str],
    ) -> None:
        job = run.job
        timestamp = self._now()
        try:
            job.returncode = await self._executor(
                argv, cwd=self.repo, on_output=job.append, cancel_event=run.cancel_event
            )
            job.phase = "completed"
        except CommandCancelled:
            job.phase = "cancelled"
        except asyncio.CancelledError:
            job.phase, job.error = "failed", "CancelledError"
            raise
        except Exception as exc:
            job.phase, job.error = "failed", type(exc).__name__
        finally:
            try:
                self._journal(
                    self.repo,
                    journal_record(
                        timestamp,
                        client,
                        journal_argv,
                        reversibility,
                        job.returncode,
                        job.command_id,
                    ),
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                job.phase, job.error = "failed", "journal_write_failed"
            if self._active_mutation is job:
                self._active_mutation = None
            job.notify()
            finished = [
                key for key, kept in self._jobs.items() if kept.job.phase != "running"
            ]
            for key in finished[:-_KEPT_FINISHED]:
                del self._jobs[key]

    async def cancel(self, body: Mapping[str, object]) -> Job:
        """Stop a running job after an explicit confirmation and return it once the command
        ended, or after ``_CANCEL_WAIT_SECONDS`` with the job still running."""
        run = self._requested(body)
        job = run.job
        confirmed = body.get("confirmed", False)
        if not isinstance(confirmed, bool):
            raise JobRejected("bad_request")
        if job.phase != "running" or run.task is None:
            raise JobRejected("not_running")
        if not confirmed:
            raise JobRejected(
                "confirmation_required",
                cancel_confirmation_message(
                    holds_mutation_slot=job is self._active_mutation
                ),
            )
        run.cancel_event.set()
        # `asyncio.wait` never cancels the task: a client disconnect leaves the execution running.
        await asyncio.wait({run.task}, timeout=_CANCEL_WAIT_SECONDS)
        return job

    def job(self, body: Mapping[str, object]) -> Job:
        """The job a request names by ``job_id``."""
        return self._requested(body).job

    def _requested(self, body: Mapping[str, object]) -> _Execution:
        job_id = body.get("job_id")
        if not isinstance(job_id, str) or not job_id or len(job_id) > MAX_ID_CHARS:
            raise JobRejected("bad_request")
        if job_id not in self._jobs:
            raise JobRejected("unknown_job")
        return self._jobs[job_id]

    async def follow(
        self, job: Job, cursor: object, *, subscribe: bool
    ) -> AsyncGenerator[dict[str, object], None]:
        """The job snapshot after `cursor`; with `subscribe`, successive non-overlapping batches
        until the job is done and its output replayed."""
        while True:
            next_change = job.next_change
            snapshot = job.snapshot(cursor)
            yield snapshot
            if not subscribe or snapshot["done"]:
                return
            cursor = snapshot["cursor"]
            if cursor == len(job.output):
                await next_change.wait()
            else:
                await asyncio.sleep(0)

    async def close(self) -> None:
        """An explicit server shutdown waits for its executions, so no command is abandoned
        half-done; subscription cancellation never does."""
        await asyncio.gather(*(asyncio.shield(task) for task in tuple(self._tasks)))
