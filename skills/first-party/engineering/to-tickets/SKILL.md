---
name: to-tickets
description: Decomposes an approved /to-spec specification and its approved Discovery Context into an ordered, verifiable set of atomic tickets with explicit dependencies and verification criteria, then publishes them after the user approves the plan. Use explicitly after /publish-epic, or on an agreed plan. Never changes production code, tests, CONTEXT.md, ADRs, or the specification's decisions.
disable-model-invocation: true
---

Invoke only on an explicit request (`/to-tickets`, or `$to-tickets` in Codex). Read
`docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md` first; if either is missing, tell
the user to run `harness update`. Read the specification, its approved paths, and the tracker.
Before approval, write only local plan drafts. After approval, write ticket files, tracker issues,
and the epic appends in `references/publish.md`. Never edit production code, tests, `CONTEXT.md`, ADRs,
or the specification's decisions. Never create branches or worktrees and never start `/implement`.

## Check the input

1. Take the epic from the user: an issue number or URL, `.scratch/<feature-slug>/spec.md`, or a spec
   path under `docs/tasks/`. Read the full body and comments.
2. Decompose a specification only when its status line is exactly `**Status** — Approved`. For any
   other status or an unresolved blocker in `## Open Questions & Risks`, list the blockers and ask
   the user to resolve them or return to `/to-spec`. Never settle a blocker yourself.
3. Child tickets need a published epic with `## Integration Branch`. If either is missing, stop
   and offer `/publish-epic`; never infer the branch.
4. Without a specification (an agreed plan or conversation only), first agree with the user on the
   missing requirements and on the Discovery Context path list. Such tickets have no parent epic,
   and their branches start from `base_branch`.

## Keep to the approved scope

- The allowlist is the spec's `## Relevant Files (Discovery Context)` plus the paths in
  `## Surgical File & Contract Changes`. Use `artifacts/discovery-context.md` only to cross-check it;
  report a mismatch and never widen the allowlist from that file.
- A ticket names only allowlisted paths. If a ticket needs another path, show the path and the
  reason in the plan and add it only after the user explicitly approves it.
- Never create a ticket for an item in `## Non-Goals & Rejected Alternatives`.

## Decompose

- Create the minimum number of tickets that implements every requirement. Do not add tickets for
  drive-by cleanup, abstractions for later, or a separate final "write all tests" step.
- Make each ticket a vertical slice that carries its change and the checks that prove it. The build
  and tests stay green after each ticket merges. For a wide blast radius, such as renaming a shared
  column, sequence expand-contract tickets: Expand, Migrate (in batches), Contract.
- Add a blocking edge only for a result dependency (the ticket uses what its predecessor delivers)
  or a known requirement incompatibility, and give its reason. File overlap alone is not a blocker.
  A blocker holds until its predecessor is merged into the integration branch and closed. Group the
  tickets into execution waves; Wave 1 has no blockers.
- Estimate, assign Discovery Context, and run the advisory sub-agent passes as described in
  `references/ticket-template.md`. If the runtime cannot dispatch a sub-agent, stop and report it.
- Draft the epic's `## Architecture invariants` and `## Implementation discipline` sections when the
  epic lacks them, using `docs/agents/agent-prompt.md`. Write only rules that hold for every ticket.

Read references/ticket-template.md when formatting the decomposition plan and ticket cards.

## Approve the plan

Before showing the plan, check that:

- every requirement `R<n>` and every acceptance criterion of the spec maps to at least one ticket
- the blocking graph has no cycles
- no ticket names an unapproved path or implements a non-goal

Save the complete plan as a new `docs/tasks/<task-folder>/artifacts/ticket-plan-v<N>.md` (the epic
folder, or a descriptive slug for a standalone plan); keep prior revisions. It holds the cards,
waves, traceability matrix, paths awaiting approval, and drafted epic sections. Record its SHA-256
and link it by absolute path. Show the full plan first. On revision, update the requested cards and
affected dependencies or coverage, repeat the checks, and show only the changed cards, dependencies,
criteria, and decisions, linking the new revision. Ask to approve that revision, including its
paths, granularity, scores, labels, and epic sections; the user may override a pipeline label
without changing the score. Wait for explicit approval.

## Publish and finish

Verify the approved draft's SHA-256 before publishing; if it is missing or changed, show a new
revision for approval. Otherwise read `references/publish.md` and follow it with that file as the
source for the configured tracker. If a write fails or the tracker is unavailable, report the error
and leave the complete ticket cards in chat.

Finish with the summary table from `references/publish.md`. Offer to adjust the tickets, or to start
a Wave 1 ticket manually with `/implement` or `/fast-implement`, matching its pipeline label.
Never invoke either skill, create branches or worktrees, or change code.
