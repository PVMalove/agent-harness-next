#!/usr/bin/env python3
"""Runtime adapter: start a headless Claude Code worker for an approved dispatch.

Claude Code cannot start a subagent in an existing checkout: the Agent tool has no working-directory
parameter, a subagent starts in the main checkout, and `EnterWorktree` refuses it there. The
`external` transport can: `coordinator.py dispatch send --adapter <this file>` runs the adapter in
`send.worker_worktree` as
`claude_worker.py dispatch [--extra-prompt-file F] [--dry-run] --repo <main repo> --brief <brief>`.
Under runtime supervision (a brief with an `execution` section) the adapter lives exactly as long as
its worker, in the same process group. Without `execution` a detached adapter manages the stream,
and the launcher returns only after the probe verdict, reporting a refused path itself.
The adapter verifies the result of a probe-only turn before sending the task to the same session;
the brief's `allowed_tools` must include plain `Bash` for that turn.
It forwards the task's native events and returns the worker's exit status. The worker's self-report,
heartbeat and `report submit`
prove its actual checkout. In a container (`HARNESS_EXECUTOR=docker`, ADR 0025) no coordinator
command can run: the prompt asks only for the staged report, and the host records the self-report
and heartbeat from the stream and submits the report. It runs on the brief's model and effort, with
exactly the brief's `allowed_tools` and `dontAsk`, so nothing outside the brief can prompt or run
unattended.
A read-only role (no file-writing tool, not `developer`) also gets `Edit(//<report_staging_path>)`,
so it can write its report and nothing else.

The installed copy is `.harness/adapters/claude_worker.py`, outside the hashed runtime package, so
installing it never changes the pinned runtime of an open batch.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import queue
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path, PurePath
from typing import NotRequired, TypedDict, cast

if __name__ == "__main__":
    sys.dont_write_bytecode = True
    import worker_write_probe  # type: ignore[import-not-found]
else:
    from harness.adapters import worker_write_probe

STARTUP_CHECK_SECONDS = 3
WRITE_PROBE_TIMEOUT_SECONDS = 45
STDERR_TAIL_LINES = 40
# Tools that already let a role write files; a role with none of them is read-only.
WRITE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
# Headless `claude -p` stops background tasks 10 minutes after the last turn and exits 0, so a
# check left in the background loses the report (#1283). The worker session cannot start one.
WORKER_ENVIRONMENT = {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"}
# The notice Claude Code prints on stderr when it stops them.
BACKGROUND_STOP_NOTICE = "Background tasks still running"
# The line the adapter adds for that stop. The coordinator reads it from the execution stderr and
# repeats the literal in harness/orchestration/workflow/execution_reaction.py; a parity test keeps
# both equal.
BACKGROUND_TASKS_STOPPED = (
    "claude worker: Claude Code stopped background tasks after the last turn"
)


class Liveness(TypedDict):
    heartbeat_every_seconds: int


class Brief(TypedDict):
    """The brief fields the adapter reads; the coordinator owns the full contract."""

    dispatch_id: str
    role: str
    resolved_model: str
    resolved_effort: NotRequired[str | None]
    allowed_tools: list[str]
    report_staging_path: str
    context_package_id: str
    liveness: Liveness
    resolved_transport: str
    purpose: str
    access: NotRequired[str]
    runtime_access: NotRequired[dict[str, object]]
    execution: NotRequired[dict[str, object]]
    context_package_summary: NotRequired[dict[str, object] | None]


class WorkerJob(TypedDict):
    command: list[str]
    probe: str
    prompt: str


# The developer skill line of a developer prompt (#1161). The adapter is stdlib-only and installed
# outside the hashed orchestration package, so it repeats the literal of
# harness/orchestration/core/developer_skill.py; a parity test keeps both equal.
DEVELOPER_SKILL_RELATIVE = ".harness/skills/developer/SKILL.md"
DEVELOPER_SKILL_INSTRUCTION = (
    "Developer skill: read the installed developer skill {path} before implementation and apply "
    "its scope, test-first and evidence discipline. The immutable brief and the developer role "
    "contract stay authoritative for assignment, scope, commits and the completion report; the "
    "skill grants no path, tool or approval. If the file is missing or unreadable, stop before "
    "any edit with outcome blocked and name the path in blockers."
)

# The contract reads of every worker prompt (#1249). The adapter is stdlib-only and installed outside
# the hashed orchestration package, so it repeats the literal of
# harness/orchestration/core/worker_contract.py; a parity test keeps both equal.
CONTRACT_ROLES_RELATIVE = ".harness/orchestration/roles"
CONTRACT_RULES_RELATIVE = ".claude/rules"
CONTRACT_INSTRUCTION = (
    "Contracts: before task work, read the common role contract {roles}/common.md and your role "
    "contract {roles}/{role}.md. Write English coordination text by {rules}/technical-english.md "
    "and Russian report text by {rules}/technical-russian.md."
)


HOST_START = """\
You are the {role} worker for dispatch {dispatch_id}.
Brief: {brief}
Report staging path: {staging}
Coordinator CLI: {cli}
Expected worker checkout: {worktree}
Expected startup SHA: {sha}
Before task work, run git rev-parse --show-toplevel, git branch --show-current and git rev-parse HEAD
in your runtime's current directory. Compare the top-level path and HEAD with the expected values
above, and the branch with the brief. Stop on any mismatch; do not reset Git history or claim
another checkout as your actual directory. Confirm your active model and the probed Git top-level:
{cli} dispatch self-report --dispatch {dispatch_id} --model "<actual active model>" --worktree "<probed Git top-level>"
Proceed only after a successful self-report; escalate a mismatch or unavailable model identity.
Immediately after self-report and at least every {heartbeat} seconds while working, run:
{cli} dispatch heartbeat --dispatch {dispatch_id}
"""

CONTAINER_START = """\
You are the {role} worker for dispatch {dispatch_id}, running in a container.
Brief: {brief}
Report staging path: {staging}
Expected worker checkout: {worktree}
Expected startup SHA: {sha}
Before task work, run git rev-parse --show-toplevel, git branch --show-current and git rev-parse HEAD
in your current directory. Compare them with the expected values above and the branch with the
brief. Stop on any mismatch; do not reset Git history.
The coordinator on the host records your model and your heartbeat from your output stream. No
coordinator command runs in this container: never run dispatch self-report, dispatch heartbeat or
report submit.
"""

WORK = """\
Context Package {package}: start from its summary in the brief. Read only the indicated
start_line-end_line ranges needed for the task.
Run every command, checks and tests included, in the foreground and wait for its result; this
session cannot run background tasks, and your final reply ends it.
{context_hint}Work within the brief; escalate a blocker for anything the brief and the package leave out.
Before your final reply, write the completion report JSON to the exact report staging path using
the common and role-specific report contract, with report_language: ru.
Use exact English enums: outcome = completed | blocked | failed; checks_run[].result = pass | fail | not_run.
Set blockers and risks (also in every review axis) to {{"status": "none", "details": ""}} when absent,
or {{"status": "present", "details": "<Russian description>"}} when present. A none status requires empty
details; present requires a non-empty description. Put other explanations in output. Strings, translated
statuses, passed and not-run are invalid; no aliases or old report formats are accepted.
"""

HOST_END = """\
Then run:
{cli} report submit --compact --file "{staging}"
Confirm the ledger receipt in one line. Relay any blocked transition or required next action.
If submission returns ledger_busy, retry after its interval. If submission otherwise fails before
recording, return the command and error as a blocker; keep the report file.
If the result includes completion, relay it to the coordinator for report complete; the report is
already recorded, so submit it only once. Chat text alone does not complete the dispatch.
"""

HOST_CONTEXT = """\
For more, read one section of the pinned package:
{cli} context-package show --dispatch {dispatch_id} --section <section>
(for example related_tests, precedent_cards, memory or goal).
"""

CONTAINER_END = """\
Then stop. The coordinator submits the staged report on the host; your final reply names the
report staging path.
"""

PROMPT = HOST_START + WORK + HOST_END
CONTAINER_PROMPT = CONTAINER_START + WORK + CONTAINER_END


def build_prompt(
    brief: Brief, brief_path: Path, repo: Path, worktree: Path, sha: str
) -> str:
    cli = " ".join(
        shlex.quote(part)
        for part in (
            sys.executable,
            str(repo / ".harness" / "orchestration" / "coordinator.py"),
            "--repo",
            str(repo),
        )
    )
    container = in_container()
    template = CONTAINER_PROMPT if container else PROMPT
    prompt = template.format(
        role=brief["role"],
        dispatch_id=brief["dispatch_id"],
        brief=brief_path,
        staging=brief["report_staging_path"],
        cli=cli,
        worktree=worktree,
        sha=sha,
        heartbeat=brief["liveness"]["heartbeat_every_seconds"],
        package=brief["context_package_id"],
        context_hint=""
        if container
        else HOST_CONTEXT.format(cli=cli, dispatch_id=brief["dispatch_id"]),
    )
    prompt += (
        CONTRACT_INSTRUCTION.format(
            roles=(repo / CONTRACT_ROLES_RELATIVE).resolve(),
            rules=(repo / CONTRACT_RULES_RELATIVE).resolve(),
            role=brief["role"],
        )
        + "\n"
    )
    if brief["role"] == "developer":
        prompt += (
            DEVELOPER_SKILL_INSTRUCTION.format(
                path=(repo / DEVELOPER_SKILL_RELATIVE).resolve()
            )
            + "\n"
        )
    if container and (brief.get("context_package_summary") or {}).get("review_focus"):
        read_context = shlex.join(
            [
                "python3",
                str(Path(__file__).resolve()),
                "context",
                "--repo",
                str(repo),
                "--brief",
                str(brief_path),
                "--section",
            ]
        )
        prompt += (
            "\nFor more of the pinned review Context Package, run "
            f"{read_context} <section>. Request only the section you need "
            "(for example related_tests, starting_files, symbol_graph or precedent_cards).\n"
        )
    if brief["role"] == "developer" and any(
        tool in brief["allowed_tools"] for tool in ("Agent", "Agent(test-author)")
    ):
        prompt += (
            "\nOptional test-author: before the first test, run "
            f"{shlex.quote(str(worktree / '.claude/hooks/test-author-preflight.sh'))} "
            f"--worktree {shlex.quote(str(worktree))} --brief {shlex.quote(str(brief_path))}. "
            "The author inherits your approved resolved_runtime, resolved_model and resolved_effort. "
            "Call Agent without model or effort overrides. Only exactly {\"status\":\"ok\"} enables "
            "the named test-author Agent; any refusal keeps ordinary TDD with its reason. "
            "Give the author the requirement, agreed seam, one scenario and a test path within "
            "the brief's allowed paths, never a proposed algorithm. "
            f"Runner log root for its Red evidence: {repo / '.harness/.sandboxes/runs'}. "
            "Wait for the author and verify its behavioral assertion before writing production code.\n"
        )
    return prompt


def check_directories(brief: Brief) -> list[Path]:
    """Directories this adapter grants beside the checkout and report: probed and created.

    The runner root is the `--add-dir` of a developer with the test author; a cache is a write
    requirement of the brief's runtime-access plan. Codex grants and probes its own set
    (`codex_worker.shared_artifact_dirs`), created without following a symlink.
    """
    directories: list[Path] = []
    if uses_test_author(brief):
        directories.append(runner_root(brief))
    plan = brief.get("runtime_access") or {}
    requirements = plan.get("filesystem")
    if isinstance(requirements, list):
        for entry in requirements:
            if (
                isinstance(entry, dict)
                and entry.get("resource") == "cache"
                and entry.get("access") == "write"
                and isinstance(path := entry.get("path"), str)
            ):
                directories.append(Path(path))
    return directories


def native_write_probe(
    brief: Brief, worktree: Path, directories: list[Path]
) -> str:
    """Put the check in the session's actual Bash tool instead of the adapter process."""
    writer = brief.get("access", "write" if brief["role"] == "developer" else "read-only") == "write"
    targets = worker_write_probe.write_targets(
        worktree, Path(brief["report_staging_path"]).parent, directories, writer=writer
    )
    return shlex.join(
        [sys.executable, str(Path(__file__).with_name("worker_write_probe.py").resolve()), *targets]
    )


def uses_test_author(brief: Brief) -> bool:
    return brief["role"] == "developer" and any(
        tool in brief["allowed_tools"] for tool in ("Agent", "Agent(test-author)")
    )


def runner_root(brief: Brief) -> Path:
    """Linked workers keep runner evidence in the main checkout's shared sandbox."""
    return Path(brief["report_staging_path"]).parents[2] / "runs"


def in_container() -> bool:
    """The container executor sets ``HARNESS_EXECUTOR=docker`` (ADR 0025)."""
    return os.environ.get("HARNESS_EXECUTOR") == "docker"


def supervised(brief: Brief) -> bool:
    """The runtime launches only briefs with an `execution` section."""
    return bool(brief.get("execution"))


def report_write_rule(staging: PurePath) -> str:
    """`Edit(//<absolute path>)` for exactly the report file; a Windows drive becomes `/c/...`."""
    posix = staging.as_posix()
    if staging.drive:
        posix = "/" + staging.drive.rstrip(":").lower() + posix[len(staging.drive) :]
    return f"Edit(/{posix})"


def worker_tools(brief: Brief) -> list[str]:
    """The brief's tools; a read-only role also gets write access to its report file only."""
    tools = list(brief["allowed_tools"])
    if brief["role"] == "developer" or any(
        tool.split("(", 1)[0] in WRITE_TOOLS for tool in tools
    ):
        return tools
    return [*tools, report_write_rule(Path(brief["report_staging_path"]))]


def resolve_claude(binary: str) -> str:
    """A bare `--claude-bin` name is looked up in PATH, then in `~/.local/bin`."""
    if os.sep in binary or (os.altsep and os.altsep in binary):
        return binary
    return (
        shutil.which(binary)
        or shutil.which(binary, path=str(Path.home() / ".local" / "bin"))
        or binary
    )


def worker_command(brief: Brief, binary: str = "claude") -> list[str]:
    """Run both turns over one native connection without session persistence."""
    command = [
        binary,
        "-p",
        "--model",
        brief["resolved_model"],
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        ",".join(worker_tools(brief)),
        "--add-dir",
        str(Path(brief["report_staging_path"]).parent),
        "--no-session-persistence",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    effort = brief.get("resolved_effort")
    if uses_test_author(brief):
        command += ["--add-dir", str(runner_root(brief))]
    if effort:
        command += ["--effort", effort]
    return command


def log_path(brief: Brief) -> Path:
    """The worker's stdout+stderr log; console observation reads it by the same rule."""
    return (
        Path(brief["report_staging_path"]).parent.parent
        / "worker-logs"
        / f"{brief['dispatch_id']}.log"
    )


def send_user_turn(process: subprocess.Popen[str], content: str) -> None:
    assert process.stdin is not None
    data = {
        "type": "user",
        "message": {"role": "user", "content": content},
        "parent_tool_use_id": None,
        "session_id": "",
    }
    process.stdin.write(json.dumps(data) + "\n")
    process.stdin.flush()


def message_blocks(event: dict[str, object]) -> list[dict[str, object]]:
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict)]


def probe_output(content: object) -> list[str]:
    if isinstance(content, str):
        return content.splitlines()
    if isinstance(content, list):
        return [
            line
            for block in content
            if isinstance(block, dict) and isinstance(text := block.get("text"), str)
            for line in text.splitlines()
        ]
    return []


def forward_native_output(
    process: subprocess.Popen[str], output: queue.Queue[str | None]
) -> None:
    assert process.stdout is not None
    try:
        for line in process.stdout:
            output.put(line)
    finally:
        output.put(None)


def forward_native_errors(
    process: subprocess.Popen[str], tail: collections.deque[str]
) -> None:
    """Pass the CLI's stderr through unchanged and keep its tail for a startup refusal."""
    assert process.stderr is not None
    for line in process.stderr:
        tail.append(line)
        sys.stderr.write(line)
        sys.stderr.flush()


def denied_bash(event: dict[str, object]) -> bool:
    denials = event.get("permission_denials")
    return isinstance(denials, list) and any(
        isinstance(item, dict) and item.get("tool_name") == "Bash" for item in denials
    )


def await_probe(output: queue.Queue[str | None], command: str) -> str | None:
    """Return the initialization event only after a successful native Bash result."""
    deadline = time.monotonic() + WRITE_PROBE_TIMEOUT_SECONDS
    tool_use_id: str | None = None
    initialized = ""
    verified = False
    while True:
        try:
            line = output.get(timeout=max(0, deadline - time.monotonic()))
        except queue.Empty:
            raise ValueError(f"native Bash write probe timed out: {command}") from None
        if line is None:
            return None
        event = json.loads(line)
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "system" and event.get("subtype") == "init":
            initialized = line
        if event_type == "assistant" and event.get("parent_tool_use_id") is None:
            for block in message_blocks(event):
                if block.get("type") != "tool_use":
                    continue
                tool = block.get("input")
                if (
                    block.get("name") != "Bash"
                    or not isinstance(identifier := block.get("id"), str)
                    or not isinstance(tool, dict)
                    or tool.get("command") != command
                    or tool.get("dangerouslyDisableSandbox") is True
                    or tool.get("run_in_background") is True
                ):
                    name = block.get("name")
                    raise ValueError(
                        f"expected the native Bash write probe, the session called "
                        f"{name if isinstance(name, str) else 'an unnamed tool'}: {command}"
                    )
                tool_use_id = identifier
        if event_type == "user" and tool_use_id is not None:
            for block in message_blocks(event):
                if block.get("type") != "tool_result" or block.get("tool_use_id") != tool_use_id:
                    continue
                result = probe_output(block.get("content"))
                if block.get("is_error") is True or worker_write_probe.SUCCESS not in result:
                    refused = next(
                        (line for line in result if line.startswith("write probe refused: ")),
                        None,
                    )
                    # A sandbox, hook or permission refusal never reaches the probe script:
                    # its own text is the cause.
                    detail = refused or (
                        f"{worker_write_probe.safe_detail(chr(10).join(result)) or 'no output'}"
                        f" ({command})"
                    )
                    raise ValueError(f"native Bash write probe failed: {detail[:1200]}")
                verified = True
        if event_type == "result":
            if not verified or event.get("is_error") is True:
                text = event.get("result")
                cause = worker_write_probe.safe_detail(text) if isinstance(text, str) else ""
                if denied_bash(event):
                    cause = (
                        "Claude Code denied the Bash tool; the role's tool_policy must allow "
                        f"plain Bash under --permission-mode dontAsk. {cause}"
                    ).strip()
                subtype = event.get("subtype")
                raise ValueError(
                    "Claude Code did not prove native Bash write access"
                    f" ({subtype if isinstance(subtype, str) else 'no subtype'}):"
                    f" {cause or 'no result text'} ({command})"
                )
            if not initialized:
                raise ValueError("Claude Code did not emit a native initialization event")
            return initialized


def write_receipt(receipt: Path | None, result: dict[str, object]) -> None:
    """Tell a detached launcher the probe verdict; replace, so a reader sees whole JSON."""
    if receipt is None:
        return
    partial = receipt.with_name(receipt.name + ".partial")
    partial.write_text(json.dumps(result), encoding="utf-8")
    partial.replace(receipt)


def run_worker(job: WorkerJob, receipt: Path | None = None) -> int:
    """Send task input only after the same CLI process completes the native probe."""
    with subprocess.Popen(
        job["command"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env={**os.environ, **WORKER_ENVIRONMENT},
    ) as process:
        assert process.stdin is not None
        output: queue.Queue[str | None] = queue.Queue(maxsize=64)
        errors: collections.deque[str] = collections.deque(maxlen=STDERR_TAIL_LINES)
        threading.Thread(target=forward_native_output, args=(process, output), daemon=True).start()
        stderr_reader = threading.Thread(
            target=forward_native_errors, args=(process, errors), daemon=True
        )
        stderr_reader.start()
        try:
            try:
                send_user_turn(
                    process,
                    "Run exactly this command once using your native Bash tool. "
                    "Keep sandbox permissions enabled. Then end this turn.\n" + job["probe"],
                )
                initialized = await_probe(output, job["probe"])
            except BrokenPipeError:
                initialized = None
            except ValueError as exc:
                write_receipt(receipt, {"ready": False, "error": str(exc)})
                raise
            if initialized is None:
                code = exit_status(process.wait(timeout=2)) or 1
                stderr_reader.join(timeout=2)
                detail = worker_write_probe.safe_detail("".join(errors)) or "no stderr"
                error = (
                    f"Claude Code exited with {code} before the native write probe finished: "
                    f"{detail}"
                )
                print(f"claude worker could not start: {error}", file=sys.stderr)
                write_receipt(receipt, {"ready": False, "error": error})
                return code
            sys.stdout.write(initialized)
            sys.stdout.flush()
            send_user_turn(process, job["prompt"])
            process.stdin.close()
            write_receipt(receipt, {"ready": True})
            while (line := output.get()) is not None:
                sys.stdout.write(line)
                sys.stdout.flush()
            code = exit_status(process.wait())
            stderr_reader.join(timeout=2)
            if any(BACKGROUND_STOP_NOTICE in line for line in errors):
                print(BACKGROUND_TASKS_STOPPED, file=sys.stderr, flush=True)
            return code
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)


def start(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    brief_path = Path(args.brief).resolve()
    brief = cast(Brief, json.loads(brief_path.read_text(encoding="utf-8")))
    if brief.get("role") == "qa":
        raise ValueError("role qa requires the coordinator QA runner")
    if brief.get("purpose") == "publish":
        raise ValueError("purpose publish requires the coordinator publish boundary")
    if brief.get("resolved_transport") != "external":
        raise ValueError("resolved_transport must be external")
    allowed = brief.get("allowed_tools")
    if (
        not isinstance(allowed, list)
        or not allowed
        or any(not isinstance(tool, str) or not tool.strip() for tool in allowed)
    ):
        raise ValueError("allowed_tools must be a non-empty list of tool names")
    if "Bash" not in allowed:
        # Under dontAsk a scoped rule such as Bash(git diff:*) denies the probe command.
        raise ValueError(
            "allowed_tools must include plain Bash: the native write probe runs through the "
            "Bash tool under --permission-mode dontAsk; add Bash to the role's tool_policy"
        )
    if (
        not isinstance(brief.get("resolved_model"), str)
        or not brief["resolved_model"].strip()
    ):
        raise ValueError("resolved_model must be a non-empty string")
    staging = Path(brief["report_staging_path"])
    incoming = repo / ".harness/.sandboxes/scratch/inbox"
    if not staging.is_absolute() or staging.parent.resolve() != incoming.resolve():
        raise ValueError(
            "report_staging_path must be in the incoming reports directory"
        )
    worktree = Path.cwd().resolve()
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    prompt = build_prompt(brief, brief_path, repo, worktree, sha)
    if args.extra_prompt_file:
        prompt += "\n" + Path(args.extra_prompt_file).read_text(encoding="utf-8")
    binary = resolve_claude(args.claude_bin)
    directories = check_directories(brief)
    job: WorkerJob = {
        "command": worker_command(brief, binary),
        "probe": native_write_probe(brief, worktree, directories),
        "prompt": prompt,
    }
    if args.dry_run:
        print(json.dumps({"cwd": str(worktree), **job}))
        return 0
    # A fresh install has no runner or cache directory yet; the probe must find them.
    worker_write_probe.prepare_directories(directories)
    if supervised(brief):
        return run_worker(job)
    log = log_path(brief)
    log.parent.mkdir(parents=True, exist_ok=True)
    receipt = log.with_name(f"{brief['dispatch_id']}.ready.json")
    receipt.unlink(missing_ok=True)
    with log.open("ab") as sink:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "_run"],
            cwd=worktree,
            stdin=subprocess.PIPE,
            stdout=sink,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    assert process.stdin is not None
    try:
        process.stdin.write(json.dumps({**job, "receipt": str(receipt)}).encode("utf-8"))
        process.stdin.close()
    except BrokenPipeError:
        process.wait(timeout=STARTUP_CHECK_SECONDS)
    # Detach only on the probe verdict: a refusal after an early return would surface later
    # as a worker that exited without a report, and its path only in the log.
    started = time.monotonic()
    deadline = started + WRITE_PROBE_TIMEOUT_SECONDS + STARTUP_CHECK_SECONDS
    while time.monotonic() < deadline:
        if receipt.exists():
            try:
                result = json.loads(receipt.read_text(encoding="utf-8"))
            except ValueError:
                time.sleep(0.02)
                continue
            if isinstance(result, dict) and result.get("ready") is True:
                # A worker that dies right after the task is still a startup failure. The window
                # opens at the verdict: a probe longer than the window would leave none of it.
                try:
                    process.wait(timeout=STARTUP_CHECK_SECONDS)
                except subprocess.TimeoutExpired:
                    return 0
                break
            process.wait(timeout=STARTUP_CHECK_SECONDS)
            error = result.get("error") if isinstance(result, dict) else None
            print(
                f"claude worker could not start: {error or 'worker startup failed'}",
                file=sys.stderr,
            )
            return 1
        if process.poll() is not None:
            break
        time.sleep(0.02)
    code = process.poll()
    if code is None:
        if sys.platform != "win32":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        code = process.wait(timeout=STARTUP_CHECK_SECONDS)
    tail = log.read_text(encoding="utf-8", errors="replace")[-500:]
    print(f"claude worker exited with {code} at startup: {tail}", file=sys.stderr)
    return 1


def exit_status(returncode: int) -> int:
    """The worker's exit code; a signal N becomes 128 + N (shell convention)."""
    return returncode if returncode >= 0 else 128 - returncode


def read_context_section(args: argparse.Namespace) -> int:
    brief = json.loads(Path(args.brief).read_bytes())
    dispatch_id = brief["dispatch_id"]
    if (
        brief.get("role") != "code-review"
        or not (brief.get("context_package_summary") or {}).get("review_focus")
        or not re.fullmatch(r"dispatch-[a-zA-Z0-9-]+", dispatch_id)
    ):
        raise ValueError("expected a compact review brief")
    runs = Path(args.repo).resolve() / ".harness/.sandboxes/runs"
    path = runs / f"review-context-{dispatch_id}.json"
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != brief["context_package_sha256"]:
        raise ValueError("review Context Package hash differs from the approved brief")
    package = json.loads(content)
    if package.get("context_package_id") != brief["context_package_id"]:
        raise ValueError("review Context Package does not match the approved brief")
    if args.section not in package:
        raise ValueError("requested section is absent from the pinned review Context Package")
    print(json.dumps({args.section: package[args.section]}, ensure_ascii=False))
    return 0


def main(argv: list[str]) -> int:
    if argv == ["_run"]:
        try:
            job = json.load(sys.stdin)
            return run_worker(cast(WorkerJob, job), Path(job["receipt"]))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            print(f"claude worker could not start: {exc}", file=sys.stderr)
            return 1
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    dispatch = sub.add_parser(
        "dispatch", help="start a worker for one approved dispatch"
    )
    dispatch.add_argument("--repo", required=True, help="main project root")
    dispatch.add_argument("--brief", required=True, help="immutable dispatch brief")
    dispatch.add_argument(
        "--claude-bin",
        default="claude",
        help="Claude Code executable; a bare name is looked up in PATH, then ~/.local/bin",
    )
    dispatch.add_argument(
        "--extra-prompt-file",
        help="text appended to the prompt (retry handoff lines)",
    )
    dispatch.add_argument(
        "--dry-run",
        action="store_true",
        help="print the command and prompt; start nothing",
    )
    dispatch.set_defaults(handler=start)
    context = sub.add_parser(
        "context", help="read one section of a container review's pinned context"
    )
    context.add_argument("--repo", required=True)
    context.add_argument("--brief", required=True)
    context.add_argument("--section", required=True)
    context.set_defaults(handler=read_context_section)
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        action = "read context" if args.command == "context" else "start"
        print(f"claude worker could not {action}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
