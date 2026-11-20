# Worktree conventions

These rules apply whenever a session works with a git worktree. The procedures for user-managed
worktrees stay in [worktrees.md](../../docs/agents/worktrees.md); the coordinator's issue worktree
procedure is in [issue-worktree.md](../../.harness/skills/implement/references/issue-worktree.md)
(`.harness/skills/implement/references/issue-worktree.md`).

- **A session that only provisions a worktree for someone else does not enter it.** `EnterWorktree` is for a session that will do the work in that branch itself. A coordinator session driving `coordinator.py` is not that: its state lives in `.harness/orchestration/state/` relative to the repository root it passes as `--repo`, so switching into the worktree forks that state into a second copy and hides the batch from the root. Such a session creates the tree with `worktree create` (see [issue-worktree.md](../../.harness/skills/implement/references/issue-worktree.md)), stays in the main checkout, and passes only the path on to the batch. The one exception is the pair that opens write access (see Session write access in [issue-worktree.md](../../.harness/skills/implement/references/issue-worktree.md)): `EnterWorktree` with `path`, then `ExitWorktree` with `action: keep`. The pair returns the session to the main checkout before the next coordinator command.
- **Never change tool configuration to make a worktree behave.** Editing `.claude/settings.local.json` — `worktree.baseRef` included — to steer one task alters the project for every later session. If the default base ref is wrong for the task, create the tree explicitly from the ref you want instead.
- **Everything else in [git-workflow.md](../../docs/agents/git-workflow.md) still applies inside a worktree** — TDD, `qa-gate` before opening a PR, the PR confirmation checkpoint, never merging. A worktree changes *where* the work happens, not the process.
