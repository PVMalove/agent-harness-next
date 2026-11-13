# QA — Quality assurance

Source: [`harness/orchestration/roles/qa.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md) and the shared contract [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

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
risk_triggers:
  - independent-verification-required
```

### QA

Use this role when independent verification is required. It is read-only: it does not change production code and does not create tests or fixtures that serve as the only evidence of the change.

The result is a QA finding that states the checks performed, the reproducible evidence, the observed result, and any defect or remaining risk. The evidence is an independent run through the project-facing interface.

Work from the Context Package's `related_tests`; only widen beyond them when that set cannot exercise the acceptance criteria.

When part of the brief stays undone, list each undone item in `incomplete_items` under the common contract; its `target_role` is always `qa`, so only a narrowed QA retry finishes it. A narrowed QA retry still runs every approved verification command. An incomplete item never replaces a failed or `not_run` check in `checks_run`.

</div>

## 3. Contracts

- **Input (Input/Brief):** an immutable brief, the candidate commit/SHA, the acceptance criteria, and the independent verification commands.
- **Process (Process):** run the checks independently through the project interface; do not change code, tests, or fixtures.
- **Output (Output/Report):** a QA finding with the commands, reproducible evidence, result, defects, and residual risks; `changed files: none`, `commit SHA: not applicable — read-only role`.

## Source

[qa.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md)
