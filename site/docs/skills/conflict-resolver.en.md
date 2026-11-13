# Conflict Resolver — Conflict resolution

Source: [`harness/orchestration/roles/conflict-resolver.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/conflict-resolver.md) and the shared contract [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## 1. Name and localization

- **English name:** `Conflict resolver`
- **Russian translation:**

```text
Разрешение конфликтов
```

## 2. Full description

Conflict Resolver is a write role for a text conflict between the ticket branch (candidate) and a moved integration SHA (target), and also for a failed CI or local-QA check of an already updated pair (`resolver.trigger: verification-failure`: there are `failed_evidence_ids`, there are no conflicting files, and the edit stays within the scope of the brief). It must not be assigned manually: the only path to it is `integration resolve`, which creates a separate resolver batch next to the completed batch of the ticket.

The role works in the issue branch and worktree of its batch, opens the `resolving-merge-conflicts` skill, preserves the requirements of both sides from the `resolver` section of the brief, and does not add functionality beyond them. It never runs `--abort` and never force-pushes. When the requirements are incompatible, it does not guess; it writes a checkpoint with a concrete description and the options. A human answer is recorded as a separate `human-decision` event, and the same dispatch continues; no new developer starts, and neighbouring batches keep running. A resolution that needs a fix of the ticket's own code is the ticket's defect: the role reports `cause: task-defect`, and the work goes to an ordinary developer.

## 3. Contracts

- **Input (Input/Brief):** the immutable brief with the `resolver` section: the ticket, the requirements of both sides, the candidate and target SHAs, the scope, the prohibitions, the commit plan, the checks, the remaining budget (two automatic target SHAs), and `report_staging_path`.
- **Process (Process):** rebase onto the exact target SHA, resolve each conflict while preserving both sides, run the project checks, commit the resolution; a checkpoint when the requirements are incompatible.
- **Output (Output/Report):** the resolution commit SHA, the exact changed files, the checks, and the `resolver` block (the preserved requirements, the human decisions, the reason, the commits according to the plan). After acceptance, the narrow route follows: no repeat review, but QA and CI or local-QA of the new pair are mandatory.

## Source

[conflict-resolver.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/conflict-resolver.md)
