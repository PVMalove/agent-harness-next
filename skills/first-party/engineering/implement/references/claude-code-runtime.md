# Claude Code runtime

Read this when the coordinator runs in Claude Code. State in the batch which worker path it uses.

**Claude Code runtime.** The Agent tool cannot select an existing checkout: a subagent starts in the
main checkout, and `EnterWorktree` refuses it there. Two paths exist; state which one the batch uses.
- `external` (strict): set the worker roles' `transport` to `external` in `.harness/orchestration.json`
  and send with `--adapter <main-repo>/.harness/adapters/claude_worker.py` (absolute path).
  `dispatch send` runs the adapter in `send.worker_worktree`, and it runs a headless `claude -p`
  there on the brief's model, effort and `allowed_tools`, so the worker's CWD is the issue worktree.
  Under the runtime (a brief with `execution`) the adapter waits for the worker in the foreground
  and exits with its code; without `execution` it detaches the worker. The adapter builds the
  prompt; for a retry, put the retry lines in a file inside the repository and pass
  `--adapter-arg=--extra-prompt-file=<path>`. A permission layer may refuse launching an agent
  from the coordinator session; that refusal is a stop, so show the developer the exact
  `dispatch send` command to run in their own terminal, then continue with `dispatch wait`.
- `in-process` (weaker evidence): the subagent's CWD is the main checkout, so the template's CWD check
  would stop it. Replace that check in its prompt: probe `git -C <worker_worktree>` for the top-level,
  branch and HEAD, run every command with `git -C` or `cd <worker_worktree> &&`, and use absolute
  paths for every file. Its self-report then proves the checkout it works in, not its CWD; say so in
  the final report.
