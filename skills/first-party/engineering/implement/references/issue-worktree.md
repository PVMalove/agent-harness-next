# Coordinator issue worktree

Read this before `batch create` and whenever this session needs write access to an existing issue
worktree. It is the coordinator's procedure; workers prepare their checkout as
`docs/agents/worktrees.md` → Worker checkout environment describes, and the branch rules are in
`docs/agents/git-workflow.md`.

A coordinator (`/implement`) must create the issue worktree before `batch create`. `batch create`
refuses a worktree that `git worktree list` does not show: `worktree '<path>' is not registered by git worktree`.
The coordinator runs these commands in the main checkout and does not work in the new worktree:

```bash
git fetch origin <integration-branch>
python .harness/orchestration/coordinator.py worktree create --repo . \
  --branch feature/issue-<ID>-<slug> --base origin/<integration-branch>
harness worktree-venv . .harness/.sandboxes/worktrees/issue-<ID>-<slug>
```

- `worktree create` asks `harness-runtime` to run `git worktree add --no-track -b <branch> <path> <base>`. The runtime works outside the agent sandbox. The sandbox mounts `.git/worktrees` read-only, so the coordinator's own `git worktree add` stops half done there. The default path is `.harness/.sandboxes/worktrees/<last branch segment>`; the runtime refuses a path outside that directory. A repeated command answers `"created": false`. `worktree remove --path <worktree>` removes a clean managed worktree the same way and keeps its branch.
- If the runtime answers `protocol_unsupported` or `unknown_operation`, it is older than this command. Update and restart `harness-runtime`, or ask the developer to run `git worktree add --no-track -b feature/issue-<ID>-<slug> .harness/.sandboxes/worktrees/issue-<ID>-<slug> origin/<integration-branch>` in a terminal outside the sandbox.

- `<integration-branch>` is the ticket's `## Integration Branch` value. If the ticket has no such section, use its `## Git base` value, then the same section of its parent epic. For a task without an epic, use `base_branch` from `.harness/project.json`. If the value is absent for a ticket that has an epic, stop and report a blocker. Do not guess it.
- In a manual `git worktree add -b`, `--no-track` is required. Without it, the command writes the upstream of the new branch to `.git/config`. In a sandbox, `.git/config` can be write-protected. The command then stops half done: the branch exists, but the worktree does not.
- `git push -u origin feature/issue-<ID>-<slug>` (see `docs/agents/git-workflow.md` section 2, step 2) sets the upstream later. It writes `.git/config` too, so it can fail the same way in a sandbox. If it fails, push with `git push origin feature/issue-<ID>-<slug>` and tell the developer that the upstream is not set.
- `harness worktree-venv` makes the worktree's `.harness/.venv` a symlink to the main checkout's venv, so brief checks such as `make lint` run without `make bootstrap`. It links only when the worktree's `uv.lock` and `pyproject.toml` match the main checkout. Otherwise it answers `"status": "refused"` with the differing files and a remedy: a separate venv in the worktree (`UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`). Do not run `make bootstrap` in a worktree with a linked venv: through the link it re-syncs the main checkout's venv. Run the command again after the recovery `git worktree add` below.
- Pass the absolute path of the worktree as `--worktree`, the branch as `--branch`, and the integration branch as `--integration-ref` to `batch create`. For a task without an epic, omit `--integration-ref`.

**Session write access.** Run the coordinator from the main checkout. After creating the
registered issue worktree, run the launch command from the operator's terminal.

```bash
python .harness/orchestration/coordinator.py --repo . worktree prepare \
  --runtime codex --worktree <issue-worktree> --launch
```

Use `--runtime claude` for Claude Code. Omit `--launch` to prepare the directories and print the
launch arguments. The command prepares shared coordinator state, report and brief staging, QA and
test runs, logs, and the npm and Playwright caches before startup.

- **Codex** applies the named permission profile to the parent session. It grants
  write access to the selected checkout, Git metadata needed for commits, and the prepared
  directories. On Linux, the default Codex network sandbox also blocks the Unix socket used by
  `harness-runtime`. To use the runtime from this session, add `--network-access enabled` if your
  policy permits it. This enables direct command networking when Codex has no active network proxy.
- **Claude Code** receives the shared directories as explicit write paths at launch: they stay
  writable while `EnterWorktree` moves the session into the worktree. The session calls `EnterWorktree`
  with the existing checkout's `path`, then immediately `ExitWorktree` with `action: keep`. The pair returns to the main checkout and keeps the worktree
  and its Git admin directory writable for this session. Run no coordinator command between the
  two calls. A new session repeats the pair. A subagent started with `isolation: worktree` cannot
  enter an existing worktree. In an existing Claude Code session, prepare the directories and call
  the same pair before working.

Run the write check through the coordinator session's shell tool inside its sandbox before dispatch.

```bash
python .harness/orchestration/coordinator.py --repo . worktree check \
  --worktree <issue-worktree>
```

Wait for `"writable": true`. The command probes the checkout, its Git admin directory, and shared
directories. Before reserving an in-process handoff, `dispatch send` repeats the checks for the
directories of the dispatched role and also probes worktree write access for write roles. Every
role requires the coordinator state, brief and report staging, and `runs/qa`; a developer also
requires `runs/tests`. A required path that is a symlink or not a directory refuses the start
(`required path is a symlink`). The logs, the caches, and runs a role does not require are optional:
a symlinked, non-directory, or unwritable one gets no write grant, a `warning: ... not granted`
line names it, and the work continues. On refusal, use the reported path to repair the session and
repeat the check.

**Empty directory after `worktree remove`.** A session that opened write access to a worktree with the `EnterWorktree` `path` and `ExitWorktree` `keep` pair keeps its path in the sandbox configuration until the session ends. Before every command, the sandbox recreates an empty directory at that path as a mount point, so the directory comes back after `worktree remove`, even when git no longer lists the worktree. The sandbox also creates mask entries relative to the session's working directory: after a `cd` into `.harness/.sandboxes/worktrees/` or `.claude/worktrees/`, a `.claude/` directory with `.cc-writes` and empty `settings.json`-like files appears there. Neither is a worktree, and `git worktree prune` does not remove it. `harness health` names such directories apart and does not warn. `harness cleanup --mode hard` removes a directory that holds only directories and empty files; a directory that a live session still mounts stays, with the reason in `skipped`. Run the cleanup after that session ends. A repeated `worktree create` with the same path works over the empty directory.

**Auto-gc and a lost issue worktree.** `git commit` and `git fetch` start an auto-gc that expires the reflogs of every worktree; under the sandbox `.git/worktrees` is read-only, and the gc fails with `cannot lock ref 'worktrees/<name>/HEAD'` after a command that succeeded. The coordinator's git commands and the agent session (the `env` block of `.claude/settings.local.json`, which `harness update` adds when the file sets none of these variables) pass `gc.auto=0` through `GIT_CONFIG_COUNT`, so the gc does not start. Run `git gc` from a terminal outside the sandbox when the repository needs it. If git no longer lists the batch's issue worktree, `dispatch preflight` and the worker self-report refuse before the role works: the message says that the worktree is lost and whether its directory is missing or empty, and the remedy is `git worktree prune && git worktree add <path> <branch>` outside the sandbox, followed by the session write-access pair.

**Recovery after a partial failure.** A repeated `worktree create` recovers by itself while the branch still points to the base. For a manual command: if `git worktree add -b` fails and `git branch --list feature/issue-<ID>-<slug>` shows the branch, the branch exists and the worktree does not. Do not create the branch again and do not delete it. Run:

```bash
git worktree add .harness/.sandboxes/worktrees/issue-<ID>-<slug> feature/issue-<ID>-<slug>
```

Before this command, check that the branch points to the commit of `origin/<integration-branch>`: `git rev-parse feature/issue-<ID>-<slug> origin/<integration-branch>`. If the branch has other commits, stop and report a blocker. Then confirm the worktree with `git worktree list`.

Before launching a worker, pass the selected absolute checkout as `--worktree` to `dispatch
preflight` and `dispatch send`. For writers it must be the batch's registered issue worktree on
its issue branch at the immutable startup SHA. Code-review retains its explicit `--checkout`;
QA and publish use their own coordinator boundaries. Send verifies the choice again and returns
`worker_worktree` and `worker_snapshot_commit` for the launch prompt. The runtime must support
starting in that existing checkout; `isolation: worktree` alone does not prove that attachment.
In Claude Code the Agent tool cannot start a subagent in an existing checkout (it starts in the main
checkout and `EnterWorktree` refuses it there). For a worker whose CWD is the worktree, use the
`external` transport with `.harness/adapters/claude_worker.py`:
`dispatch send --adapter <main-repo>/.harness/adapters/claude_worker.py` runs it in `worker_worktree`
and it runs a headless `claude -p` there: in the foreground for the worker's whole run under the
runtime (a brief with `execution`), detached otherwise. An `in-process` subagent works through absolute
paths and `git -C <worker_worktree>`; its self-report proves the checkout it works in, not its CWD.
The worker probes and self-reports its actual canonical Git top-level, branch and HEAD. A main
checkout at the same SHA is still the wrong path for a writer. Keep the coordinator and its CLI
repo/state address in the main checkout. Never reset a candidate to satisfy a stale brief.
