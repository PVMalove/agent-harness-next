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
typecheck from `qa_gate_commands` have run. The seam is agreed with the human before the first test, then the work goes through `/tdd`. The skill
finishes with a human-readable report in the chat with five sections: changes, checks (pass, fail or
not run), unverified items, risks and blockers. The skill does not commit, push, open a PR, run code
review or change tracker labels. In `/fast-implement` it runs the implementation steps, and
`/fast-implement` keeps review, commit, push and the `/to-pull-requests` handoff.

## Orchestration role `developer`

The interactive skill and the coordinator's `developer` role are different. Inside a dispatch, the role
manifest and the brief apply; the skill neither repeats nor widens them. The role contract follows.

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

Use this role for ordinary changes to a backend service that stay within the explicit allowed paths of the brief. Do not perform work on the data schema or a data migration, or work on the outbox, the message schema, routing, retries, or the DLQ; these specialized triggers belong to the respective roles.

The result is an implementation that meets the acceptance criteria of the handoff. Prove it with the targeted and mandatory checks of the project, and with a risk review when a listed trigger applies. Pass every check through the installed bounded summary wrapper; report only the command, the status, the failed test, and a short sanitized error. Keep the full output in its local artifact path, never in the handoff or in a later worker's chat.

Locate the seam through the Context Package's `starting_files` and `symbol_graph` before searching the repository; re-run a failing test by its node id through the bounded wrapper, not the full suite.

</div>

The remaining sections of the manifest:

- **Red-Green-Refactor with the test author.** When the test-author preflight returns exactly `{"status":"ok"}`, the developer runs each implementation step as one test-first cycle with a separate `test-author`. Any other preflight answer keeps ordinary TDD. The cycle creates no new dispatch, role, state, or ledger record.
- **Developer-retry.** A retry continues from `snapshot_commit` with new commits (fix-forward). Amend, squash, reset, rebase, and force-push of `snapshot_commit` or a commit below it are forbidden. A brief with a non-null `rebase_target_commit` first requires a rebase onto exactly that target, then the fix.
- **Blocked commit.** When a hook or another tool blocks `git commit`, the developer reverts nothing. It stops with `tooling_blocker` and lists the uncommitted files in `uncommitted_files`.
- **Commit plan.** The developer follows the brief's commit plan. In the primary and rebase dispatch, the mapping of commits to plan entries is many-to-many. In a developer-retry, each new commit closes exactly one plan entry. `commit_map` is mandatory when the brief has a `commit_plan`.
- **Carried items.** A developer-retry closes each `carried_items` entry with new commits and records it in `carried_item_closure`, or marks it `not_closed` with the reason.
- **Rerunning only failed tests.** After a failure, the developer reruns only what failed: `scripts/verify.py --worktree-cache --only tests` or `--failed-only`. Such a result is only a diagnostic: it does not replace the brief's `verification_commands` in `checks_run` and does not allow publishing.

## 3. Contracts

- **Input (Input/Brief):** the immutable coordinator brief with the explicit write allowed paths, the DoD, the branch/worktree, the prohibitions, and the verification commands.
- **Process (Process):** implement only within the allowed paths of the brief on the issue branch and in the isolated worktree; run the targeted and mandatory checks, and, for a risk trigger, the required review.
- **Output (Output/Report):** the implementation, the commit SHA, the exact changed files, the checks performed, the residual risks, and the blockers.

## Source

[developer.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md)
