# Decomposition plan and ticket cards

## Estimation and pipeline

- Give every `afk` ticket a Fibonacci story-point score from `story_points.scale` in
  `.harness/project.json`, or `1, 2, 3, 5, 8, 13…` when it is absent. The score is a
  decomposition-quality signal, not a commitment. `hitl` tickets get no score.
- If a score equals `story_points.gray_zone` (default `4`), run one advisory sub-agent call for that
  ticket alone. If the two scores disagree, keep the higher one.
- Derive the label from the final score: `pipeline::fast` when the score is at most
  `story_points.fast_threshold` (default `3`), `pipeline::full` when it is at least
  `story_points.full_threshold` (default `5`). Only `afk` tickets get a `pipeline::*` label.
- Flag a score of 13 or more with `⚠️ score ≥13 — split further`.
- Take the estimated hours for a person from `story_points.hours` in `.harness/project.json`:
  the value for the ticket's final score. Show `—` for a `hitl` ticket or when the mapping has no
  value for that score.
- Do not name a model for any sub-agent call: it runs on the model the runtime assigns to sub-agents.

## Discovery Context per ticket

- Assign every allowlisted path to every ticket it materially supports; a shared path may belong to
  several tickets. Keep the path's note and add one short ticket-specific reason. Show a path that
  supports no ticket as **unassigned** and ask the user; never assign it artificially.
- Build one **Path inventory** for the batch: each allowlisted path, every path in its containing
  directory, and existing `tests/` and `shared/` directories next to them. Apply the repository's
  default exclusions (secrets, dependencies, build output, caches, generated or minified files,
  large logs, databases, temporary data, unrelated media). Keep an explicitly approved file even if
  it matches an exclusion. Add a root-level file as that file, never the repository root. Do not
  read or send file contents or symbol signatures.
- Run one advisory sub-agent call per batch. Give it the ticket titles, scopes, assigned paths, and
  the Path inventory, and ask only for additions: exact Path inventory paths per ticket, each with a
  reason. Discard suggestions outside the Path inventory or unrelated to the ticket. Show every
  accepted suggestion in the plan as a new path that needs the user's approval.

## Plan layout

1. **Waves** — one line per wave with its tickets, for example `Wave 1: 01, 02 · Wave 2: 03 (after 01)`.
2. **Traceability matrix** — one row per requirement:

   | Requirement | Acceptance criterion | Tickets |
   | --- | --- | --- |
   | `R1` | <criterion from the spec> | `01`, `03` |

3. **Ticket cards** — in dependency order, using the card below.
4. **Paths awaiting approval** — each new path with its ticket and reason.
5. **Epic sections** — the drafted `## Architecture invariants` and `## Implementation discipline`,
   or which existing section or project default stays.

## Ticket card (plan)

- **ID & Title:** `<NN>` — short descriptive name
- **Labels / Type:** `type::*`, `hitl` or `afk`, and for `afk` the score, the estimated hours, and
  the `pipeline::*` label
- **Blocked by / Wave:** each blocking ticket with its reason, or `None — can start immediately`; the wave
- **What to build:** what the ticket delivers, in one to three sentences
- **Contract touchpoints:** the allowlisted files to change or create and the signatures, schemas,
  or contracts affected
- **Out of scope:** what this ticket must not touch, such as work owned by a neighbouring ticket
- **Acceptance criteria:** `Action -> Verify` items with the exact test or command for each
- **Relevant Files (Discovery Context):** assigned and approved paths, each with its reason

## Local ticket file

`.scratch/<feature-slug>/issues/<NN>-<slug>.md`:

```markdown
# <NN> — <Ticket title>

**Category:** type::bug / type::feature / type::refactoring / type::chore / type::security / type::performance / type::hotfix
**Workflow:** status::ready (or status::blocked)
**Execution:** hitl / afk
**Execution wave:** <N>
**Story Points:** <score> (afk only; omit the line for hitl)
**Pipeline:** pipeline::fast / pipeline::full (afk only; omit the line for hitl)
**Task report:** required (omit the line if not required)
**Integration branch:** <exact branch recorded by the parent epic>
**Blocked by:** <ticket numbers or titles, each with its reason, or "None — can start immediately">

## What to build
<What the ticket delivers.>

## Contract touchpoints
- `<path>` — <change and the contract or signature affected>

## Out of scope
- <What this ticket must not touch.>

## Relevant Files (Discovery Context)
- `<path>` — <why this ticket needs it>

## Acceptance criteria
- [ ] <Action> -> <Verify: exact test or command>
```

## Tracker issue body

```markdown
## Parent: #<epic>

## Integration Branch

<exact branch recorded by the parent epic>

## What to build
<What the ticket delivers.>

## Execution wave
<N>

## Story Points
<score> (afk only; omit the section for hitl)

## Contract touchpoints
- `<path>` — <change and the contract or signature affected>

## Out of scope
- <What this ticket must not touch.>

## Relevant Files (Discovery Context)
- `<path>` — <why this ticket needs it>

## Acceptance criteria
- [ ] <Action> -> <Verify: exact test or command>

## Blocked by
- Blocked by #<M> — <reason>, one line per blocking ticket, or "None — can start immediately"
```

Keep `## Parent: #<epic>` exactly in this form and never translate it: the frontier query reads it.
Omit it for a ticket without a parent epic, together with `## Integration Branch`. Omit
`## Relevant Files (Discovery Context)` when there is no Discovery Context. Keep file paths in the
path sections; elsewhere include code only as a short prototype snippet that records a decision.
