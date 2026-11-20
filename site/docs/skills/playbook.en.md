# Playbook — Orchestration playbook

Source: [`harness/orchestration/playbook.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/playbook.md).

## 1. Name and localization

- **English name:** `Backend Batch Orchestration Playbook`
- **Russian translation:**

```text
Руководство по оркестрации backend-batch
```

## 2. Full description

The Playbook is a runtime-neutral coordination contract for the optional `backend-orchestration` capability. It defines the coordinator's manual protocol, not a dispatch mechanism, a provider choice, or a mandatory runtime adapter. The primary source defines the coordinator's authority, the immutable briefs and reports, the batch state machine, the role order, the liveness rules, the parallelism conditions, the quality gates, and the baseline metrics.

The coordinator alone accepts a completion report, manages the lifecycle, approves dispatches, and handles scope changes. Each batch has one ticket, one issue branch, and one isolated worktree; one write role is active at a time. A change of scope, zone, DoD, purpose, or required evidence ends the dispatch and requires a new immutable brief.

The Context Package is an immutable, ledger-owned result of the deterministic `context_builder.py`. The roles of one batch
reuse it. Before each dispatch, the coordinator checks the freshness of the existing package in shadow
mode: it records the result but does not block the dispatch. The role package registered for the dispatch must be fresh, otherwise the dispatch is refused. A checkpoint is a separate non-terminal record for the write role only; it allows a new
worker session to start under the same dispatch ID without carrying over the chat history and traceback. A recognized rate limit
authorizes the resume automatically; a planned trigger requires an existing coordinator decision.

There is no mandatory base-freshness gate: review verifies the pinned candidate even if the integration base
moved ahead. PR preparation on a moved base goes through `integration refresh`, which rebases only the batch's
issue branch onto the exact target SHA.
A delta-review is either test-only (after a Warning, only for a test-only diff) or follows a fix-forward:
the coordinator chooses the delta-review or the full review itself, without a separate human decision; the dispatch
is approved under `approval_policy` together with this choice. The conditions for a full review are described in
[`code-review`](code-review.md). Any delta-review is always a new independent
review dispatch. An advisory tool call remains an ephemeral non-role output and cannot authorize
work.

`approval_policy: auto` defines an automatic path from `batch approve` to an accepted publish.
The policy approves the batch, each dispatch, and a planned continuation. `batch auto-decide` makes a
decision on the report from the ledger facts: accept a clean report with risks, or retry by `route_preview`.
Each decision is written as `policy:auto` with evidence. Conditions from a closed list of categories (`integrity-failure`,
`budget-exhausted`, `no-automatic-route`) stop the path, and the coordinator writes a final report. After
a stop, a human approves each step. Only a human opens a PR, and auto-merge is prohibited.

## 3. Contracts

- **Input (Input/Brief):** the ticket, allowed paths, issue branch/worktree, DoD, prohibitions, verification commands, provider/model assignment, and explicit human approval.
- **Process (Process):** `planned → awaiting-approval → active → awaiting-approval`, and ends in `completed` or `abandoned`. Only a human returns a batch from `blocked`, `failed`, or `paused`. `not-required` remains as a legacy terminal record; new commands write `completed`. The Architect precedes the Developer; reports are accepted only with sufficient independent evidence.
- **Output (Output/Report):** the Context Package, checkpoints, immutable dispatch briefs, completion reports, the accepted final batch status, and the observed metric baseline.

## 4. Architecture diagram

![Backend orchestration: batch lifecycle](../diagrams/previews/backend-batch.lifecycle.png)

## Source

[playbook.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/playbook.md)
