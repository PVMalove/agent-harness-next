# Developer — Developer

Source: [`harness/orchestration/roles/developer.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md) and the shared contract [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

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
