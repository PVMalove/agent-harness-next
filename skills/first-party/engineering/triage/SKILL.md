---
name: triage
description: Triages incoming issues and external PRs: sets type, execution mode, route and status labels, verifies the claim, and posts an agent brief or closes as wontfix. Use explicitly for raw reports; not for tickets that /to-tickets created.
disable-model-invocation: true
---

# Triage

Move issues on the project issue tracker through a small state machine of triage roles.

If this repo treats external pull requests (merge requests on GitLab) as a request surface (see the issue-tracker config), triage covers them too: **a PR is an issue with attached code** — same roles, same states, same machine. When a PR or MR is in scope, read [references/pull-requests.md](references/pull-requests.md) for its deltas.

## Reference docs

- [AGENT-BRIEF.md](AGENT-BRIEF.md) — how to write durable agent briefs
- [OUT-OF-SCOPE.md](OUT-OF-SCOPE.md) — how the `.out-of-scope/` knowledge base works

## Roles

This project uses a namespace-based, enterprise-style label taxonomy. Every triaged issue carries exactly one `type::*` label and exactly one `status::*` label; while it carries `status::specs` the execution-mode axis below doesn't apply yet (see that role), otherwise it also carries exactly one of `hitl`/`afk`. Optional `priority::*`/`severity::*` labels are purely informational and not part of this required-axis check. If any required axis ends up with zero or multiple labels, flag it and ask the maintainer before doing anything else.

**Type** (`type::*`):

- `type::bug` — something is broken
- `type::feature` — new feature or improvement
- `type::refactoring` — internal restructuring, no behavior change
- `type::chore` — maintenance, tooling, or dependency upkeep
- `type::security` — security fix or hardening
- `type::performance` — performance improvement
- `type::hotfix` — urgent production fix

**Status** (`status::*`) — where it sits in the pipeline:

- `status::specs` — design/spec-writing: an epic or large task still being turned into a spec and decomposed into tickets (applied by `/publish-epic` to a new epic and when triage routes an existing epic-sized issue). Too early to take into development; execution mode isn't decided yet.
- `status::ready` — fully specified, ready to be picked up (by an agent if `afk`, by the maintainer if `hitl`)
- `status::in-progress` — currently being worked on in an active session
- `status::blocked` — blocked, either by another ticket's dependency or because triage is waiting on more information from the reporter (post triage notes either way, see the triage notes template below)

**Execution mode** — who does the work (required once an issue leaves `status::specs`):

- `hitl` — human-in-the-loop; needs architectural review, testing, or approval from the maintainer
- `afk` — away-from-keyboard; an agent can complete it alone

**Route** (`pipeline::*`) — `afk` only. A `status::ready` + `afk` issue carries exactly one: `pipeline::fast` for a small change with a settled direction, otherwise `pipeline::full`. `/fast-implement` takes only `pipeline::fast` and `/implement` only `pipeline::full`, so without it the issue reaches no implementation route. Triage computes no story points.

**Context labels** — applied when relevant, not part of the required axes above:

- `resolution::wontfix` — the request was explicitly rejected. Applied at close time (see "Apply the outcome" below), not during normal triage.

`task-report::required` is a context label outside the triage workflow. `/publish-epic` applies it to an epic and `/to-tickets` to child tickets. `/to-pull-requests` acts on it. See `docs/agents/triage-labels.md`.

An unlabeled issue is implicitly "needs triage" — there is no dedicated label for that state, it's just the absence of the required axes.

These are the actual label strings for this repo. See `docs/agents/triage-labels.md`.

Never apply upstream canonical labels (`ready-for-agent`, `ready-for-human`, `needs-triage`, `needs-info`, `wontfix`) or an `epic::<slug>` label. This repo groups a ticket under an epic with the tracker's parent link — a GitHub sub-issue, on GitLab a `## Parent: #<epic>` section plus a `relates_to` issue link, or the local-markdown folder structure (see `docs/agents/issue-tracker.md#wayfinding-operations`); explain that if the maintainer asks for an epic label.

State transitions: analyze an unlabeled issue to determine its `type::*` label and whether it's `hitl` or `afk`, then place it in `status::ready` (with the agreed `pipeline::*` for `afk`) or `status::blocked` (dependency or missing info) — or, if it's too large to specify in one triage pass, `status::specs` and point the maintainer at `/to-spec`. `status::blocked` returns to `status::ready` once the blocker clears or the reporter replies — `/to-pull-requests` sweeps a closed ticket's dependents, and `/implement`/`/fast-implement` re-check blockers in pre-flight; `triage` does not run that sweep on its own initiative. The maintainer can override at any time — flag transitions that look unusual and ask before proceeding.

## Tracker commands

Before the first tracker command (list, comment, label change, close), read [references/tracker-commands.md](references/tracker-commands.md). Issue text and comment bodies follow the Project-Only Metadata rule in `docs/agents/git-workflow.md` §1: they describe the project and carry no generated-by or AI-generated mark.

## Invocation

The maintainer invokes `/triage` and describes what they want in natural language. Interpret the request and act. Examples:

- "Show me anything that needs my attention"
- "Let's look at #42" (issue or PR)
- "Move #42 to status::ready"
- "What's ready for agents to pick up?"

## Show what needs attention

Query the issue tracker and present three buckets, oldest first:

1. **Unlabeled** — never triaged.
2. **Missing one of the required axes** — partially triaged, evaluation in progress.
3. **`status::blocked` with reporter activity since the last triage notes** — needs re-evaluation.

Show counts and a one-line summary per item. Let the maintainer pick.

## Triage a specific issue or PR

1. **Gather context.** Read the full issue or PR (body, comments, labels, author, dates; for a PR, the diff too). Parse any prior triage notes so you don't re-ask resolved questions. Explore the codebase using the project's domain glossary, respecting ADRs in the area. Run two checks against the codebase: (a) **redundancy** — search for an existing implementation of the requested behavior by domain concept (not just the request's wording), and report where you looked. If found, it's an already-implemented rejection, handled under `resolution::wontfix` (step 5). (b) **prior rejection** — read `.out-of-scope/*.md` and surface any that resembles this request.

2. **Recommend.** Tell the maintainer your recommended type (`type::*`), execution mode (`hitl`/`afk`), status and, for `afk`, the route (`pipeline::fast` for a small change with a settled direction, otherwise `pipeline::full`), with reasoning, plus a brief codebase summary relevant to the request — including whether it's already implemented. If the request is epic-sized (too big to specify in this pass), recommend `status::specs` and point at `/to-spec` instead of a state/mode pair. Wait for direction.

3. **Verify the claim.** Before any grilling, check that the claim holds up. For a bug, reproduce it from the reporter's steps. For a PR, confirm the diff does what it claims — check it out, run the relevant tests or commands. Report what happened: confirmed (with code path), failed, or insufficient detail (a strong signal to route to `status::blocked` pending more info). A confirmed verification makes a much stronger agent brief.

4. **Grill (if needed).** If the request needs fleshing out, run `/grilling` with `/domain-modeling` — grill it into shape a round of questions at a time, sharpening domain terms and applying `/grilling`'s `references/domain-doc-writes.md` before any glossary or ADR edit. Use the grilling verdict in step 5: `kill` → Rejected; `needs-clarification` → `status::blocked` with the blocking unknowns in the triage notes; `go` → `status::ready` or `status::specs`.

5. **Apply the outcome:**
   - `status::ready` + `afk` + the agreed `pipeline::*` — post an agent brief comment ([AGENT-BRIEF.md](AGENT-BRIEF.md)).
   - `status::ready` + `hitl` — same brief structure, but note why it can't be delegated (judgment calls, external access, design decisions, manual testing).
   - `status::specs` — point the maintainer at `/to-spec` to turn this into a proper spec and decomposition; don't write an agent brief for it.
   - `status::blocked` — post triage notes (template below): a dependency ticket to wait on, or missing info from the reporter.
   - Rejected — apply `resolution::wontfix`, remove any `status::*` label, and close, with the comment depending on *why*:
     - **Already implemented** — the change already exists in the codebase. Point to where it lives; do **not** write to `.out-of-scope/` (that KB is for *rejected* requests, not built ones).
     - **Rejected (bug-shaped report)** — polite explanation, then close. Skip the `.out-of-scope/` write — that KB is for rejected requests, not invalid bug reports.
     - **Rejected (feature/behavior request)** — write to `.out-of-scope/`, link to it from a comment, then close ([OUT-OF-SCOPE.md](OUT-OF-SCOPE.md)).
   - Still unlabeled after step 1–4 (partial progress only) — leave it unlabeled, or apply just the axis you've resolved. Optional comment noting what's settled so far.

## Quick state override

If the maintainer says "move #42 to status::ready", trust them and apply the label directly — ask only if the execution mode (`hitl`/`afk`) or, for `afk`, the route (`pipeline::*`) isn't already clear from context. Confirm what you're about to do (label changes, comment, close), then act. Skip grilling. If moving to `status::ready` + `afk` without a grilling session, ask whether they want to write an agent brief.

## Triage notes template (for `status::blocked`)

```markdown
## Triage Notes

**What we've established so far:**

- point 1
- point 2

**What we still need from you (@reporter):**

- question 1
- question 2
```

Capture everything resolved during grilling under "established so far" so the work isn't lost. Questions must be specific and actionable, not "please provide more info".

## Resuming a previous session

If prior triage notes exist on the issue or PR, read them, check whether the reporter has answered any outstanding questions, and present an updated picture before continuing. Don't re-ask resolved questions.
