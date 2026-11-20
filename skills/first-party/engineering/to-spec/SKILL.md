---
name: to-spec
description: Turns grilling results and approved Discovery Context into a verifiable technical specification. Use explicitly after /grilling, /grill-me, or /grill-with-docs, or to specify an agreed design. Leaves production code untouched.
disable-model-invocation: true
---

Invoke only on an explicit request (`/to-spec`, or `$to-spec` in Codex). Load this file by itself
before any repository exploration, then read repository evidence only within the approved scope.
Use the project's language and keep the template headings intact. Write only the approved spec file.
Never modify production code, tests, project configuration, `CONTEXT.md`, ADRs, or Discovery Context.
Never create tasks, publish, or change Git state.

## Load the handoff

1. Identify the task folder under `docs/tasks/` by `docs/agents/artifacts.md`, including the epic
   folder for a child task. Look for `artifacts/discovery-context.md` there before treating the
   handoff as a cold start. Propose the spec file at the root of that folder.
2. Check `docs/tasks/.../artifacts/discovery-context.md` for this task and the final grilling summary in chat.
   Import the goal and scope, accepted decision IDs and selected option numbers, rejected alternatives and
   their reasons, open questions, assumptions, and confirmed glossary and ADR updates. Clarify decision
   gaps that affect the design. Copy option numbers only where supplied. On a `kill` verdict, stop and
   report its decisive reason; write no spec. On `needs-clarification`, carry each blocking unknown into
   the open questions and ask whether to resolve them first or write a partial spec.
3. Use the task's nonempty, approved Discovery Context as the file allowlist.
   Preserve the approved lines in order, including any supplied context. If chat and the artifact
   disagree on the approved list, ask the user to reconcile them before relying on disputed paths.
4. If the artifact is missing or empty or cannot be verified, ask the user to approve the minimum
   path list. Use explicitly approved paths from the final summary as the proposed list when available.

## Approve evidence paths

- List candidate paths without reading file contents. Use user-provided names or scoped path listings.
  Show each proposed repo-relative path and why it is needed. Ask which paths to add to Discovery Context.
- Wait for explicit approval before reading or citing a candidate. Apply the same rule to any new
  code, tests, configuration, glossary, or ADR path discovered while assembling the spec.
- Keep declined paths out of repository reads and the change plan. Get fresh approval before using
  a previously declined path. Preserve the rejected approach and rationale without naming an unapproved file.
- Keep newly approved paths in chat for this session. Preserve the approved artifact on disk as supplied.
  Use the resulting allowlist for evidence, proposed changes, and verification paths.
- Run key unresolved architectural choices through the protocol after the user approves the path list.

## Decision & Clarity Protocol

Use this protocol for architecture or contract blockers from a partial handoff and new choices about
contracts, schemas, integrations, failure handling, or edge cases. Keep accepted choices settled.
For each unresolved fork, stop assembling the specification and do the following.

1. Give 2–3 sentences explaining the choice and verified facts from approved files. Identify any missing evidence.
2. Render a matrix in a fenced `text` block with box-drawing borders. Give each option a header and
   separate rows for mechanism, benefit, and cost. Name concrete contract or component changes.
   - **[1] Рекомендуемое (Recommended)** — mechanism, reason to prefer it, and trade-off.
   - **[2] Компромиссное (Fast-Track)** — simplification, delivery gain, debt, and when to rule it out.
   - **[3] Полное (Full / Clean Architecture)** — target design, long-term benefit, and adoption cost.
   If there are fewer than three technically distinct options, explain why and omit unsupported options.
3. Offer the displayed numbers as choices. Record only an explicit selection of a displayed number,
   with its decision ID and profile. Keep the reasons for rejecting the other approaches.
4. Offer `подробнее 1`, `подробнее 2`, `подробнее 3` for displayed options and `подробнее все`.
   Read `references/drill-down-template.md` when the user requests `подробнее <N>` (or `details <N>`).
   `все` / `all` expands every displayed option. Reply in chat without writing any files.
   Then show the same choices again and wait. A detail request never approves an option or a write.

Wait for an explicit choice or an explicit instruction to save a Draft, writing nothing meanwhile.

## Approve and write the specification

Read `references/spec-template.md` when assembling the specification.
Use `Approved` when all blocking choices are settled and the user approves the scope and verification.
Use `Draft — has open blockers` only at the user's explicit request. Record each blocker, its dependent
work, and the decision needed to proceed. Leave unresolved implementation details unspecified.
Review the requirements before approval. Pick the highest-impact risks from the agreed scope,
handoff, and approved evidence. For each, identify the covering requirement and observable
criterion, or ask how missing or ambiguous in-scope behavior should work. Use the
Decision & Clarity Protocol for unresolved contracts. Repeat affected checks after revisions. Verify that:

- every repository file cited in the spec is approved and each proposed edit is tied to the goal
- accepted decisions and rejection reasons agree with the handoff
- every functional requirement has a verifiable acceptance criterion, a test seam, and a check
- the status and blockers match the current decisions

Present the review findings with the scope, first demonstrable scenario if applicable, status,
verification approach, and proposed path. Wait until the user explicitly approves writing to the
proposed path, including an overwrite if the file exists. Honor approval already given for the
same scope, verification, status, and write. A numbered design choice approves only that choice.
Create only directories needed for the approved file. Apply the same gates to revisions.

## Finish

Return the saved path and status. If the write fails, report the error and return the complete specification in chat.
Offer revisions or, for an Approved spec, a manual next step: `/publish-epic` and then `/to-tickets`,
or `/implement` when its prerequisites are met. For a Draft, offer to resolve the blockers first. Never invoke either skill automatically.
