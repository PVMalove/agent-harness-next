# Parallel work: git worktrees { #parallel-work-git-worktrees }

This guide covers user-managed parallel worktrees and the issue worktree that a coordinator
prepares before `batch create`. The coordinator protocol is in `.harness/orchestration/playbook.md`.

For running more than one feature branch at once without one session's dirty working tree stepping on another's, use Claude Code's native `EnterWorktree` / `ExitWorktree` tools — not manual `git worktree add` + a separate terminal multiplexer. Where `tmux` is installed, `EnterWorktree` attaches a `tmux` session to the worktree automatically and `ExitWorktree` manages its lifecycle (`keep` leaves it running, `remove` kills it) — nothing to configure either way. Where it isn't (e.g. no `tmux`/no full Linux distro under WSL), `EnterWorktree` still gives the same isolation without it.

## When to use it { #when-to-use-it }

Only when explicitly asked — by the developer directly, or by this doc. Don't reach for a worktree on a normal single-branch task; the regular issue-branch + PR flow in [git-workflow.md](git-workflow.md) covers that. Use a worktree when the developer wants to work on (or have an agent work on) more than one ticket in parallel, so each gets its own working directory and branch instead of sharing one.

For a subagent spawned via the `Agent` tool to work on an independent ticket in parallel, pass `isolation: "worktree"` on that call instead of manually creating one — same underlying mechanism, scoped to that subagent.

## Conventions { #conventions }

Three mandatory items below — "A session that only provisions a worktree…", "Never change tool configuration…" and "Everything else in git-workflow.md…" — ship as the runtime rule `.claude/rules/worktree-conventions.md` (source `harness/project/rules/worktree-conventions.md`). Claude Code loads it automatically; Codex reads it through the pointer in the Runtime section of `AGENTS.md`. The installed `.harness/instructions/worktrees.md` has one pointer item in their place.

- **Branch naming still applies.** `EnterWorktree`'s `name` parameter drives the new branch name, but it is not copied verbatim: the runtime has been observed to prefix it and to replace `/`, turning `feature/issue-366-checkout-quote` into `worktree-feature+issue-366-checkout-quote` — which does not satisfy `branch_pattern` in `.harness/project.json` (see [git-workflow.md](git-workflow.md#2-workflow-sequence)). Check the branch the tool actually created and rename it before committing anything. Don't let it default to a random name for ticket work.
- **A session that only provisions a worktree for someone else does not enter it.** `EnterWorktree` is for a session that will do the work in that branch itself. A coordinator session driving `coordinator.py` is not that: its state lives in `.harness/orchestration/state/` relative to the repository root it passes as `--repo`, so switching into the worktree forks that state into a second copy and hides the batch from the root. Such a session creates the tree with `worktree create` (see the [issue worktree procedure](../skills/implement.md#issue-worktree)), stays in the main checkout, and passes only the path on to the batch. The one exception is the pair that opens write access (see Session write access in the [issue worktree procedure](../skills/implement.md#issue-worktree)): `EnterWorktree` with `path`, then `ExitWorktree` with `action: keep`. The pair returns the session to the main checkout before the next coordinator command.
- **Never change tool configuration to make a worktree behave.** Editing `.claude/settings.local.json` — `worktree.baseRef` included — to steer one task alters the project for every later session. If the default base ref is wrong for the task, create the tree explicitly from the ref you want instead.
- **Base ref**: a fresh worktree for a child ticket branches from the epic's recorded `origin/<integration-branch>`; an epic-less task uses `origin/<base_branch>` from `.harness/project.json`. Use the current local `HEAD` only when the task specifically requires it (`worktree.baseRef` setting).
- **Everything else in [git-workflow.md](git-workflow.md) still applies inside a worktree** — TDD, `qa-gate` before opening a PR, the PR confirmation checkpoint, never merging. A worktree changes *where* the work happens, not the process.
- **Cleanup**: once a ticket in a worktree is done and its PR is merged (or the ticket is abandoned), exit with `ExitWorktree`. Use `remove` for a finished/abandoned ticket, `keep` only if the developer wants to return to it later. Don't leave worktrees accumulating under `.claude/worktrees/`.
- **Managed harness worktrees**: create coordinator and CLI-owned issue checkouts under the main checkout's `.harness/.sandboxes/worktrees/`. Preview stale clean worktrees with `harness cleanup <repo> --mode hard`; `--apply --confirm HARD` removes eligible directories and their local branches. Worktrees on `integration/*` branches and clean detached-HEAD worktrees (e.g. for code review) qualify too once their commits are on `origin`; detached worktrees have no branch to delete. Ledger-referenced, dirty, current, and unpushed worktrees stay in place. Remote branches stay in place.

## Coordinator issue worktree { #coordinator-issue-worktree }

The coordinator (`/implement`) owns the procedure for the issue worktree: `worktree create`,
`harness worktree-venv`, session write access, auto-gc, recovery after a partial failure and the
choice of the worker checkout. Its source for agents is
`.harness/skills/implement/references/issue-worktree.md` (installed with `engineering-suite`); the
translation is in the [implement skill description](../skills/implement.md#issue-worktree).

## Worker checkout environment { #worker-checkout-environment }

A worker prepares the issue worktree without touching the main checkout's environment:

- **Python checks** (`make lint` and the brief's pytest commands): the coordinator runs `harness worktree-venv <repo> <worktree>` once. A worktree checkout, rebase or merge gives `pyproject.toml` and `uv.lock` a new mtime without changing them; never re-sync the linked venv for that, and never shift file mtimes to hide it. In the harness repository, `make` runs `scripts/sync_dev_venv.py` instead of `uv sync`: for a linked venv it compares both files with the main checkout and does not sync, and when they differ it refuses with the remedy (a venv of the worktree).
- **Browser e2e (Playwright):** under the sandbox the home cache (`~/.cache/ms-playwright`) is read-only, so `playwright install` fails there. Set `PLAYWRIGHT_BROWSERS_PATH` to the main checkout's `.harness/.sandboxes/cache/ms-playwright`; for `npm ci`, `~/.npm` is read-only too, so pass `npm_config_cache=<main>/.harness/.sandboxes/cache/npm`. Build the frontend before every e2e run: a spec on an older build reports old failures. In the harness repository, `npm run test:e2e` in `harness/console/frontend` does all three: it builds `dist`, picks the browser directory, installs Chromium (a no-op when it is there), and runs Playwright with the arguments after `--`.
- **Network for a first install:** `registry.npmjs.org` for `npm ci`; `cdn.playwright.dev` and `storage.googleapis.com` (Chrome for Testing) for Chromium. Add them to the sandbox's allowed domains for that command. Without them, the worker reports the e2e check as `not_run` and names the blocked host.
