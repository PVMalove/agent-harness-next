# Developer — Developer

Source: [`harness/orchestration/roles/developer.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md) and the shared contract [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## 1. Name and localization

- **English name:** `Developer`
- **Russian translation:**

```text
Разработчик
```

## 2. Full translation of the role manifest

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

The result is an implementation that meets the acceptance criteria of the handoff. Prove it with the targeted and mandatory checks of the project, and with a risk review when a listed trigger applies.

</div>

## 3. Contracts

- **Input (Input/Brief):** the immutable coordinator brief with the explicit write allowed paths, the DoD, the branch/worktree, the prohibitions, and the verification commands.
- **Process (Process):** implement only within the allowed paths of the brief on the issue branch and in the isolated worktree; run the targeted and mandatory checks, and, for a risk trigger, the required review.
- **Output (Output/Report):** the implementation, the commit SHA, the exact changed files, the checks performed, the residual risks, and the blockers.

## Source

[developer.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md)
