# Code Review — Code review

## 1. Name and localization

- **English:** Code Review
- **Russian (1:1):**

```text
Ревью кода
```

## 2. Full description

Code Review is an independent read-only role, mandatory for every risk trigger in its manifest: API/public contracts, schema/data migrations, outbox/queues, message schema routing, transactions, authorization/security, concurrency/retry, and retry/DLQ. Other changes may use it after an explicit risk assessment. The role does not change production code and does not integrate the branch under review.

It reviews the diff and the Context Package, not the whole tree; an insufficient package is a blocker to escalate, not a reason to walk the repository at large. Its report records the fixed diff and the originating requirement as evidence, then returns two independent axes: Standards and Spec. They must not be reduced to a single score or replaced by one of them. The coordinator does not complete a high-risk batch until both axis reports are present: a missing report blocks the batch.

A deviation from the letter of the brief is a finding, not automatically a retry. When the implemented form is functionally equivalent to the one the brief named or safer, the role reports a `warning` with that assessment, so the coordinator can record `override-warning` and keep the candidate. The role sets `review.recommendation` to `accept` or `retry`; the configured `auto_retry_min_severity` decides which severities cause an automatic retry.

## 3. Contracts

- **Input (Input/Brief):** the immutable brief, the fixed diff/commit range, the originating specification, the project standards, and the list of applicable risk triggers.
- **Output (Output/Report):** separate Standards and Spec findings with severity; the pinned diff and requirement evidence; the residual risks, the blockers, and the absence of production changes.

## Source

[code-review.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/code-review.md)
