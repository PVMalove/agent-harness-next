---
name: to-tickets
description: Decomposes an approved /to-spec specification and its approved Discovery Context into an ordered, verifiable set of atomic tickets with explicit dependencies and verification criteria, then publishes them after the user approves the plan. Use explicitly after /publish-epic, or on an agreed plan. Never changes production code, tests, CONTEXT.md, ADRs, or the specification's decisions.
disable-model-invocation: true
---

Invoke only on an explicit request (`/to-tickets`, or `$to-tickets` in Codex). Read
`docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md` first; if either is missing, tell
the user to run `harness update`. For decomposition, read the specification, its approved paths, and
the tracker. Write nothing until the user approves the plan. Then write only ticket files, tracker
issues, and the epic appends in `references/publish.md`. Never edit production code, tests,
`CONTEXT.md`, ADRs, or the specification's decisions, and never start `/implement`.

## Check the input

1. For `--review <epic>`, follow `references/acceptance-review.md` and return before decomposition.
2. Take the epic from the user: an issue number or URL, `.scratch/<feature-slug>/spec.md`, or a spec
   path under `docs/tasks/`. Read the full body and comments.
3. Decompose a specification only when its status line is exactly `**Status** — Approved`. For any
   other status or an unresolved blocker in `## Open Questions & Risks`, list the blockers and ask
   the user to resolve them or return to `/to-spec`. Never settle a blocker yourself.
4. Child tickets need a published epic with `## Integration Branch`. If either is missing, stop
   and offer `/publish-epic`; never infer the branch.
5. Without a specification (an agreed plan or conversation only), first agree with the user on the
   missing requirements and on the Discovery Context path list. Such tickets have no parent epic,
   and their branches start from `base_branch`.

## Keep to the approved scope

- The allowlist is the spec's `## Relevant Files (Discovery Context)` plus the paths in
  `## Surgical File & Contract Changes`. Use `artifacts/discovery-context.md` only to cross-check it;
  report a mismatch and never widen the allowlist from that file.
- A ticket names only allowlisted paths. If a ticket needs another path, show the path and the
  reason in the plan and add it only after the user explicitly approves it.
- Never create a ticket for an item in `## Non-Goals & Rejected Alternatives`.
- Copy each applicable, verifiable non-goal from that section into the affected ticket's
  `## Out of scope`. Keep the rationale for rejected alternatives in the spec.

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
- When `## Goal & Scope` names a **First demonstrable scenario**, put its tickets in the earliest
  feasible wave, mark them in the wave plan, and show the check that proves its result on its own.
- Read references/ticket-template.md when formatting the decomposition plan and ticket cards.
  Estimate, assign Discovery Context, and run the advisory sub-agent passes as described there.
  If the runtime cannot dispatch a sub-agent, stop and report it.
- Draft the epic's `## Architecture invariants` and `## Implementation discipline` sections when the
  epic lacks them, using `docs/agents/agent-prompt.md`. Write only rules that hold for every ticket.

## Approve the plan

Before showing the plan, check that:

- every requirement `R<n>` and every acceptance criterion of the spec maps to at least one ticket
- the IDs in each ticket criterion agree with the traceability matrix
- the ticket criteria preserve the epic's obligations as checked in `references/acceptance-review.md`
- the blocking graph has no cycles
- no ticket names an unapproved path or implements a non-goal

Show the cards, waves, traceability matrix, paths awaiting approval, and drafted epic sections. Ask
whether granularity, blocking edges, scores, pipeline labels, and epic sections are right; the user
may override a pipeline label without changing the score. Wait for explicit approval. For requested
changes, revise only the named tickets, rerun the acceptance review, and show the plan again.

## Publish and finish

After approval, read `references/publish.md` and follow it for the configured tracker. If a write
fails or the tracker is unavailable, report the error and leave the complete ticket cards in chat.
Finish with its summary table. Offer to adjust the tickets or to start a Wave 1 ticket manually with
`/implement` or `/fast-implement`, matching its pipeline label. Never invoke either skill, create
branches or worktrees, or change code.
