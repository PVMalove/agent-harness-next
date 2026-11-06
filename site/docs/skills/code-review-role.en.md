# Code Review — Code review

## 1. Name and localization

- **English:** Code Review
- **Russian (1:1):**

```text
Ревью кода
```

## 2. Full description

Code Review is an independent read-only role, mandatory for API/public contracts, schema/data migrations, outbox/queues, transactions, authorization/security, concurrency/retry, and retry/DLQ. For other changes, the coordinator starts it after an explicit risk assessment. The role does not change production code and does not integrate the branch under review.

It pins the fixed diff and the originating requirement, then returns two independent axes: Standards and Spec. They must not be reduced to a single score or replaced by one of them. A missing report for any mandatory axis blocks the completion of a high-risk batch.

## 3. Contracts

- **Input (Input/Brief):** the immutable brief, the fixed diff/commit range, the originating specification, the project standards, and the list of applicable risk triggers.
- **Output (Output/Report):** separate Standards and Spec findings with severity; the pinned diff and requirement evidence; the residual risks, the blockers, and the absence of production changes.

## Source

[code-review.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/code-review.md)
