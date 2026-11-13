#!/usr/bin/env python3
"""Runtime adapter: start a headless Claude Code worker for an approved dispatch.

Claude Code cannot start a subagent in an existing checkout: the Agent tool has no working-directory
parameter, a subagent starts in the main checkout, and `EnterWorktree` refuses it there. The
`external` transport can: `coordinator.py dispatch send --adapter <this file>` runs the adapter in
`send.worker_worktree` as
`claude_worker.py dispatch [--extra-prompt-file F] [--dry-run] --repo <main repo> --brief <brief>`.
Under runtime supervision (a brief with an `execution` section) the adapter lives exactly as long as
its worker: it runs `claude -p <prompt>` in the foreground in its own process group, never reads its
own stdin, streams `--output-format stream-json --verbose` to the inherited stdout (the runtime's run
log) and returns the worker's exit status. Without `execution` it starts a detached `claude -p` that
reads the prompt from stdin and returns. The worker's self-report, heartbeat and `report submit`
prove its actual checkout. It runs on the brief's model and effort, with exactly the
brief's `allowed_tools` and `dontAsk`, so nothing outside the brief can prompt or run unattended.
A read-only role (no file-writing tool, not `developer`) also gets `Edit(//<report_staging_path>)`,
so it can write its report and nothing else.

The installed copy is `.harness/adapters/claude_worker.py`, outside the hashed runtime package, so
installing it never changes the pinned runtime of an open batch.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePath
from typing import NotRequired, TypedDict, cast

STARTUP_CHECK_SECONDS = 3
# One argv string is bounded by MAX_ARG_STRLEN (131072 bytes) on Linux; a Windows command line by
# 32767 characters in all. Keep a margin for the other arguments.
POSIX_PROMPT_BYTES = 120000
WINDOWS_PROMPT_CHARS = 30000
# Tools that already let a role write files; a role with none of them is read-only.
WRITE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})


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
    execution: NotRequired[dict[str, object]]


PROMPT = """\
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
Context Package {package}: start from its starting_files, symbol_graph and
related_tests. For a starting file with non-empty sections, read only the start_line-end_line
ranges the task needs.
Work within the brief; escalate a blocker for anything the brief and the package leave out.
Before your final reply, write the completion report JSON to the exact report staging path using
the common and role-specific report contract, with report_language: ru.
Use exact English enums: outcome = completed | blocked | failed; checks_run[].result = pass | fail | not_run.
Set blockers and risks (also in every review axis) to {{"status": "none", "details": ""}} when absent,
or {{"status": "present", "details": "<Russian description>"}} when present. A none status requires empty
details; present requires a non-empty description. Put other explanations in output. Strings, translated
statuses, passed and not-run are invalid; no aliases or old report formats are accepted.
Then run:
{cli} report submit --file "{staging}"
Completion means the report is recorded in the ledger. Include the submit result in your final reply.
If submission returns ledger_busy, retry after its interval. If submission otherwise fails before
recording, return the command and error as a blocker; keep the report file.
If the result includes completion, relay it to the coordinator for report complete; the report is
already recorded, so submit it only once. Chat text alone does not complete the dispatch.
"""


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
    prompt = PROMPT.format(
        role=brief["role"],
        dispatch_id=brief["dispatch_id"],
        brief=brief_path,
        staging=brief["report_staging_path"],
        cli=cli,
        worktree=worktree,
        sha=sha,
        heartbeat=brief["liveness"]["heartbeat_every_seconds"],
        package=brief["context_package_id"],
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


def supervised(brief: Brief) -> bool:
    """The runtime launches only briefs with an `execution` section."""
    return bool(brief.get("execution"))


def check_prompt_bound(prompt: str) -> None:
    if os.name == "nt":
        too_long = len(prompt) > WINDOWS_PROMPT_CHARS
        bound = f"{WINDOWS_PROMPT_CHARS} characters"
    else:
        too_long = len(prompt.encode("utf-8")) > POSIX_PROMPT_BYTES
        bound = f"{POSIX_PROMPT_BYTES} UTF-8 bytes"
    if too_long:
        raise ValueError(
            f"the worker prompt exceeds the argument bound of {bound}; "
            "shorten --extra-prompt-file"
        )


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


def worker_command(
    brief: Brief, binary: str = "claude", *, prompt: str | None = None
) -> list[str]:
    """The `claude -p` command; a given `prompt` (supervised) is the positional after `-p`.

    `--allowedTools` and `--add-dir` take variadic values, so the prompt must precede them.
    """
    command = [binary, "-p"]
    if prompt is not None:
        command.append(prompt)
    command += [
        "--model",
        brief["resolved_model"],
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        ",".join(worker_tools(brief)),
        "--add-dir",
        str(Path(brief["report_staging_path"]).parent),
        "--no-session-persistence",
        "--output-format",
    ]
    command += ["stream-json", "--verbose"] if prompt is not None else ["text"]
    effort = brief.get("resolved_effort")
    if brief["role"] == "developer" and any(
        tool in brief["allowed_tools"] for tool in ("Agent", "Agent(test-author)")
    ):
        # Linked workers keep runner evidence in the main checkout's shared sandbox.
        command += [
            "--add-dir",
            str(Path(brief["report_staging_path"]).parents[2] / "runs"),
        ]
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
    if supervised(brief):
        check_prompt_bound(prompt)
        command = worker_command(brief, binary, prompt=prompt)
    else:
        command = worker_command(brief, binary)
    if args.dry_run:
        print(json.dumps({"cwd": str(worktree), "command": command, "prompt": prompt}))
        return 0
    if supervised(brief):
        # Foreground in the adapter's process group: the runtime's group stop reaches the
        # worker, and the worker's exit is the supervised process's exit.
        completed = subprocess.run(
            command, cwd=worktree, stdin=subprocess.DEVNULL, check=False
        )
        return exit_status(completed.returncode)
    log = log_path(brief)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as sink:
        process = subprocess.Popen(
            command,
            cwd=worktree,
            stdin=subprocess.PIPE,
            stdout=sink,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    assert process.stdin is not None
    try:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
    except BrokenPipeError:
        process.wait(timeout=STARTUP_CHECK_SECONDS)
    time.sleep(STARTUP_CHECK_SECONDS)
    code = process.poll()
    if code is not None:
        tail = log.read_text(encoding="utf-8", errors="replace")[-500:]
        print(f"claude worker exited with {code} at startup: {tail}", file=sys.stderr)
        return 1
    return 0


def exit_status(returncode: int) -> int:
    """The worker's exit code; a signal N becomes 128 + N (shell convention)."""
    return returncode if returncode >= 0 else 128 - returncode


def main(argv: list[str]) -> int:
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
        print(f"claude worker could not start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
