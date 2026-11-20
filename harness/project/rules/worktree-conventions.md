# Worktree conventions

These rules apply whenever a session works with a git worktree. The procedures for user-managed
worktrees stay in [worktrees.md](../../.harness/instructions/worktrees.md); the coordinator's issue worktree
procedure is in [issue-worktree.md](../../.harness/skills/implement/references/issue-worktree.md).

- **A session that only provisions a worktree for someone else does not enter it.** `EnterWorktree` is for a session that will do the work in that branch itself. A coordinator session stays in the main checkout, because entering the worktree forks the coordinator state under `--repo` and hides the batch; it creates the tree and opens write access as issue-worktree.md describes.
- **Never change tool configuration to make a worktree behave.** Editing `.claude/settings.local.json` — `worktree.baseRef` included — to steer one task alters the project for every later session. If the default base ref is wrong for the task, create the tree explicitly from the ref you want instead.
- **Everything else in [git-workflow.md](../../.harness/instructions/git-workflow.md) still applies inside a worktree** — TDD, `qa-gate` before opening a PR, the PR confirmation checkpoint, never merging. A worktree changes *where* the work happens, not the process.
