# record-qa-gate-pass

## 1. Name and localization
- **English name:** record-qa-gate-pass
- **Translation / Gist:**

```text
Recording a successful QA Gate pass
```
## 2. Full description
The `qa-gate` skill calls the `record-qa-gate-pass.sh` script directly (see `SKILL.md`) as its last step, right after all commands from `qa_gate_commands` succeed. The skill runs in an isolated (forked) context and cannot rely on the `mark-qa-gate-passed.sh` hook (PostToolUse) firing reliably for tool calls inside that fork. So the skill writes the marker of a successful test pass itself. The `qa-gate` and `to-pull-requests` skills take the script path from `CLAUDE_PROJECT_DIR`. If the variable is not set (second runtime), they take it from the main worktree: the first entry of `git worktree list --porcelain` where `.claude/hooks/` is installed.

The `to-pull-requests` skill calls the same script from the PR branch checkout after `coordinator.py qa evidence` has confirmed the current SHA. The script writes the coordinator's accepted QA evidence to the marker without a repeated QA-gate run.

The script computes the current project state from the hash of the last commit (`git rev-parse HEAD`) and the hash of the current uncommitted changes (`git diff HEAD | git hash-object --stdin`). It writes the resulting composite state hash to the file `.claude/.qa-gate/passed`. This confirms that the current code state passed the quality check.
## 3. Contracts
- **Input (Input/Brief):** The optional environment variable `CLAUDE_PROJECT_DIR` (default: the current directory `.`), which points to the project root directory. The current working directory selects the checkout for which the marker is written, so run the script from the checkout of the tested branch or the PR branch.
- **Output (Output/Report):** Creation or update of the marker file `.claude/.qa-gate/passed`, which contains a string of the form `<HEAD_hash>:<diff_hash>`.
## Source

[record-qa-gate-pass.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/record-qa-gate-pass.sh)
