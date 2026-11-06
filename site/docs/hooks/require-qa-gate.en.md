# require-qa-gate

## 1. Name and localization
- **English name:** require-qa-gate.sh
- **Translation / Gist:**

```text
Blocking PR/MR creation without a successful QA pass
```
## 2. Full description
This `PreToolUse(Bash)` hook intercepts commands in the agent's bash terminal. Its main task is to block the `gh pr create` command (creating a pull request) or the `glab mr create` command (creating a merge request) if the agent has not first run a successful check, with the `qa-gate` skill, of the checkout whose branch is being published.

The hook analyzes its input (the bash command text from stdin). If the command text contains `gh pr create` or `glab mr create`, or their alias `gh pr new`/`glab mr new`, the hook determines the checkout of the published branch and builds a hash of its state (the HEAD hash + the hash of the current changes). Then it checks that the marker file `.claude/.qa-gate/passed` exists in that checkout and that its content matches. The `qa-gate` skill creates this marker when it succeeds. If the marker is missing or its content does not match the computed state, the hook stops the execution with an error and a message that `qa-gate` must run. If the command does not create a PR/MR, or the check passed, the hook exits with code 0 and allows the command to run.

Instead of the marker, the hook accepts accepted QA evidence from the orchestration coordinator. It requests `qa evidence` from `.harness/orchestration/coordinator.py` of the main worktree, for the ticket from `issue-<N>` in the branch name and the `HEAD` of the checkout. The hook writes nothing to the ledger records. The CLI itself takes the ledger lock while it reads, so the call is limited to 60 seconds, and a busy or unavailable coordinator keeps the previous block. The evidence is accepted if the CLI confirmed the `accept` decision, the report is unchanged, and `candidate_commit` matches `HEAD`; the report must have `outcome: completed` and `result: pass` for every command in `qa_gate_commands`, and `git diff HEAD` must be empty. The report commands are compared literally with the `qa_gate_commands` lines: the QA lane runs the `verification_commands` of the dispatch, and if they differ from `qa_gate_commands`, the evidence is not accepted and the marker path remains. Failed, unaccepted, and `blocked` reports, a different SHA, a dirty tree, and a missing coordinator all keep the previous marker path, so `/fast-implement` and work outside orchestration do not change.

The branch comes from the argv of the create command itself (parsed by `pr_commands.py`). Flags of other commands on the same line, for example `git commit -s`, do not count as a branch:
- `gh pr create`: `--head <branch>`, `--head=<branch>`, or the short `-H <branch>`, `-H<branch>`, `-H=<branch>` (including inside a flag group, `-dH <branch>`). The `owner:` prefix is dropped.
- `glab mr create`: `-s <branch>`, `-s<branch>`, `-s=<branch>`, `--source-branch <branch>`, `--source-branch=<branch>`, including inside a group of short flags (`-fs <branch>`). The glab flag `-H`/`--head` sets the repository (`OWNER/REPO`), not the branch, and is ignored.
- Without a branch flag, the hook checks the deepest project checkout that contains the payload `cwd`, that is, the current branch.

The branch selection is no narrower than in the previous version: if the text contains `gh pr create`, the first `--head <branch>`/`--head=<branch>` in the whole command text (global `shlex.split` parsing, as in the previous hook) also counts as the PR branch and is checked, even if the token-based parse of the create command does not see it. A `--head` without a value, or text with `--head` that `shlex` did not parse, blocks the call.

Exactly one linked worktree must correspond to the branch found; otherwise the call is blocked.

The hook recognizes PR/MR creation by the command text: a mention of `gh pr create`/`gh pr new` or `glab mr create`/`glab mr new` in quotes or in the argument of another command also starts the check of the checkout from `cwd`. The merge ban in `block-pr-merge.sh` does not affect this recognition. Ambiguous cases are also blocked: more than one different branch (from create commands and the global `--head` parse), a branch flag without a value, and create text that cannot be parsed into tokens and contains a branch flag. Any hook error gives exit code `2`, including a missing, incomplete, or syntactically broken `pr_commands.py` next to the hook.
## 3. Contracts
- **Input (Input/Brief):** The input stream (stdin) with the bash command and `cwd`. The current git repository state (HEAD and uncommitted changes) of the checkout of the published branch.
- **Output (Output/Report):** Exit code `0` (the command may run) or exit code `2` with an error message in `stderr` (the command is blocked).
## Source

[require-qa-gate.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/require-qa-gate.sh), [qa-gate-state.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/qa-gate-state.py), [pr_commands.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/pr_commands.py)
