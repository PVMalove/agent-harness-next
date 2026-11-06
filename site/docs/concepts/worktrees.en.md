# Worktrees

Several tasks at the same time do not require several clones of the repository. A Git worktree is a second
working copy of the same repository on another branch: the files are separate, the history is shared.

## When

- A long task is running, and you need to look at or check another branch.
- Two agents work in parallel, and each must have its own clean directory.
- You need a run that must not touch the uncommitted edits of the main work.

A worktree is created at the explicit request of a human. If an agent creates a worktree on its own, it
changes the structure of its workspace, which the human did not order.

## Native worktrees

Runtimes can create and remove worktrees with native tools. The branch name is
checked by the same rule as when you create a branch normally: it must match the
`branch_pattern` of the project. The check also fires on the worktree tool — otherwise the rule would be bypassed
by switching the tool.

## Coordinator and the ticket worktree

A pipeline with gates creates the worktree before it plans the batch, because the batch refuses to work with a
worktree that is not in the list of working copies. The base is the integration branch of the ticket, not the current
branch and not the release branch.

- The work runs in the ticket's own worktree; the main copy stays clean.
- Unfinished worktrees are visible in `harness health` as a separate check, so an abandoned copy does not
  turn into invisible garbage.
- `worktree-remove` removes a managed worktree and keeps the branch: removing the directory must not
  mean losing work.

## What goes into a worktree

A worktree receives the project snapshot and the contracts for agents — that is, everything that describes the project.
Operational data is not copied: the project memory index and the orchestration record are shared across the repository.

The memory index is read from a worktree read-only: a copy of the index per worktree would quickly diverge from
the original, and the search is needed across the whole corpus anyway. Writes to the index are protected against parallel
processes, so two simultaneous builds do not corrupt it.

## Next

- ["/implement"](../guides/implement.md)
- [Workflow](../guides/workflow.md)
