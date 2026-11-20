# Developer — Developer

## Interactive skill developer { #developer_1 }

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/developer/SKILL.md).
The skill ships in `engineering-suite` and implements an agreed change in the current issue branch in an
ordinary session, outside a coordinator dispatch. Before it edits any file, it checks three prerequisites:
a task with acceptance criteria (an existing ticket when the repository has an Issue First rule), a
readable `.harness/project.json` with `branch_pattern` and `base_branch`, and a current branch that matches
`branch_pattern` and is neither `base_branch` nor `integration/*`. When a prerequisite is missing, the
skill changes nothing and returns a report with a blocker that names it.

The ticket's `## Relevant Files (Discovery Context)`, `## Contract touchpoints` and
`## Out of scope` bound the change; a path outside them needs the human's approval. The work is
complete when the `Verify` commands of the acceptance criteria, the targeted tests, and lint and
typecheck from `qa_gate_commands` have run or are listed as unverified with the reason. The seam is agreed with the human before the first test, then the work goes through `/tdd`. The skill
finishes with a human-readable report in the chat with five sections: changes, checks (each acceptance criterion with its `[R<n>]` IDs and `Verify` command, then other
commands; pass, fail or not run), unverified items, risks and blockers. The skill does not commit, push, open a PR, run code
review or change tracker labels. In `/fast-implement` it runs the implementation steps, and
`/fast-implement` keeps review, commit, push and the `/to-pull-requests` handoff. For a labeled afk
ticket (`pipeline::*`), the description points to `/fast-implement` or `/implement` instead.

## Orchestration role `developer`

The interactive skill and the coordinator's `developer` role are different. Every developer dispatch
reads the installed skill: `dispatch send` and `dispatch resume` return a `developer_skill` field with
the absolute path `<repo>/.harness/skills/developer/SKILL.md` and the prompt line, and the Claude and
Codex adapters add the same line themselves. The worker applies the skill's discipline (scope,
test-first, evidence), but the brief and the role manifest stay authoritative: the brief's accepted
design replaces the agreement with the human, the role's machine-readable report replaces the chat
report, and the commit plan decides commits. The skill grants no path, tool or approval. Without the
installed skill, both commands refuse before any ledger or brief change; a worker that cannot read
the file stops with `outcome: blocked` and the path in `blockers`. The role contract follows.

Source: [`harness/orchestration/roles/developer.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md) and the shared contract [`common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/common.md).

## 1. Name and localization

- **English name:** `Developer`
- **Russian translation:**

```text
Разработчик
```

## 2. Full translation of the role manifest

The translation covers the manifest header and its introduction. The remaining sections are summarized below; the full text is in the English source.

<div class="ah-skill-text" markdown="1">

```yaml
name: developer
mode: write
required_capabilities:
  - backend-development
risk_triggers:
  - api-public-contract
  - transactions
  - authorization-security
  - concurrency-retry
```

### Developer

Use this role for ordinary changes to a backend service that stay within the explicit allowed paths of the brief. Schema or data migration, outbox, message-schema, routing, retry and DLQ work has no dispatch route yet (#1159): when the brief needs it, escalate through the ordinary blocker path.

The result is an implementation that meets the brief's `definition_of_done`. Prove it with the targeted and mandatory project checks. When the change touches a risk trigger, name it in the optional report field `risk_triggers` with the trigger names of the `code-review` role manifest; `report submit` refuses an unknown name. Run every check through the installed bounded summary wrapper. Report only the command, the status, the failed test and a short sanitised error. Keep the full output in its local artifact path, never in the handoff or in the next worker's chat.

Locate the seam through the Context Package's `starting_files` and `symbol_graph` before searching the repository; re-run a failing test by its node id through the bounded wrapper, not the full suite.

</div>

The remaining sections of the manifest:

- **Red-Green-Refactor with the test author** (`references/developer-test-author.md`, before the first test). The cycle comes from `tdd/references/test-author.md`; the role adds its own rules: the seam from `accepted_design.output`, the blocker path, one preflight command. When the test-author preflight returns exactly `{"status":"ok"}`, the developer runs each implementation step as one test-first cycle with a separate `test-author`. Any other preflight answer keeps ordinary TDD. The cycle creates no new dispatch, role, state, or ledger record.
- **Developer-retry** (`references/developer-retry.md`). A retry continues from `snapshot_commit` with new commits (fix-forward). Amend, squash, reset, rebase, and force-push of `snapshot_commit` or a commit below it are forbidden. A brief with a non-null `rebase_target_commit` first requires a rebase onto exactly that target, then the fix.
- **Blocked commit.** When a hook or another tool blocks `git commit`, the developer reverts nothing. It stops with `tooling_blocker` and lists the uncommitted files in `uncommitted_files`.
- **Commit plan.** The developer follows the brief's commit plan. In the primary and rebase dispatch, the mapping of commits to plan entries is many-to-many. In a developer-retry, each new commit closes exactly one plan entry. `commit_map` is mandatory when the brief has a `commit_plan`.
- **Carried items** (`references/developer-carried-items.md`). A developer-retry closes each `carried_items` entry with new commits and records it in `carried_item_closure`, or marks it `not_closed` with the reason.
- **Rerunning only failed tests** (`references/developer-rerun-failed-tests.md`, only when the project has `scripts/verify.py`). After a failure, the developer reruns only what failed: `scripts/verify.py --worktree-cache --only tests` or `--failed-only`. Such a result is only a diagnostic: it does not replace the brief's `verification_commands` in `checks_run` and does not allow publishing.

## 3. Contracts

- **Input (Input/Brief):** the immutable coordinator brief with the explicit write allowed paths, the DoD, the branch/worktree, the prohibitions, and the verification commands.
- **Process (Process):** implement only within the allowed paths of the brief on the issue branch and in the isolated worktree; run the targeted and mandatory checks, and, for a risk trigger, the required review.
- **Output (Output/Report):** the implementation, the commit SHA, the exact changed files, the checks performed, the residual risks, and the blockers.

## Source

[developer.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md)
