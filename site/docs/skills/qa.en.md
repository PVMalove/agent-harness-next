# QA — Quality assurance

Source: [`harness/orchestration/roles/qa.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md) and the shared contract [`common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/common.md).

## 1. Name and localization

- **English name:** `QA`
- **Russian translation:**

```text
Обеспечение качества
```

## 2. Full translation of the role manifest

<div class="ah-skill-text" markdown="1">

```yaml
name: qa
mode: read-only
required_capabilities:
  - independent-verification
```

### QA

Use this role when an independent verification is required. No worker session receives it: the coordinator runs QA through `qa run`, and the clean-room QA runner executes the brief's `verification_commands` on the exact candidate and writes the report itself. The worker adapter refuses a QA brief, and `report submit` refuses a QA report written by hand.

The report lists every approved command in `checks_run`; a command the run never reached is `not_run`. A failed command routes a developer retry. QA never changes production code or authors the tests and fixtures that prove the change.

</div>

## 3. Contracts

- **Input (Input/Brief):** an immutable brief, the candidate commit/SHA, the acceptance criteria, and the independent verification commands.
- **Process (Process):** the coordinator runs `qa run`; there is no model worker.
- **Output (Output/Report):** the clean-room QA runner's report: every approved command in `checks_run` with `pass`, `fail` or `not_run`; `changed files: none`, `commit SHA: not applicable — read-only role`.

## Source

[qa.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md)
