# To Tickets — Into tickets

## 1. Name and localization

- **English name:** `To Tickets`
- **Russian translation:**

```text
В тикеты
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: to-tickets
description: Break a plan, a specification, or a conversation into a set of tracer-bullet tickets with blocking edges, and publish them to the configured tracker.
disable-model-invocation: true
```

### Into tickets

**Objective:** break a plan, a specification, or a conversation into a set of **tickets** — tracer-bullet vertical slices, each declaring its blocking edges.

The issue tracker and the triage label vocabulary should already have been provided to you in `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`. If either file is missing, tell the user to run `harness update` — it creates both files from the harness templates.

#### Execution in two phases

Run this skill in two phases: publish nothing to the issue tracker and create no local files until the user explicitly approves the ticket breakdown.

##### Phase 1: drafting and review

1. **Gather context:** work from the conversation context. If a reference is passed (a specification path, an issue number/URL), read its full body and comments.
2. **Explore the codebase (optional):** use the project's domain glossary. Look for prefactoring opportunities ("make the change easy, then make the easy change").
3. **Draft the vertical slices:** break the work into **tracer bullet** tickets.
   - *Vertical slices:* cut a narrow but COMPLETE path through every layer (schema, API, UI, tests). It must be demoable/verifiable on its own and fit in one context window.
   - *Wide refactors (exception):* if a change has a huge blast radius (for example, renaming a shared column), use **expand-contract** instead of vertical slicing. The sequence is: Expand → Migrate (in batches) → Contract.
   - *Blocking edges:* give each ticket its blocking edges (which other tickets must complete first). Add a blocker only for a **result dependency** (the ticket uses what its predecessor delivers) or a **known requirement incompatibility** (the two requirements cannot both hold until the predecessor lands — for example, one removes what the other still needs; a textual merge conflict is not one), and write the substantive reason for each one. A **file overlap** alone is not a blocker: two independent changes to one file proceed in parallel, without artificial sequencing. A blocker holds until the predecessor is merged into the integration branch and closed — a push, a publish, an accepted QA, or an open PR does not release it.
   - *Story Points:* give every `afk` ticket a Fibonacci story-point score, using `story_points.scale` from `.harness/project.json` when it is present, otherwise `1, 2, 3, 5, 8, 13…`. This is a signal of the decomposition quality, not a commitment. `hitl` tickets never receive a score — skip this field for them.
   - *Escalation pass:* if a ticket's primary score equals `story_points.gray_zone` (default `4`), make one cheap-model advisory call for that ticket alone (`model: haiku` or the cheapest configured equivalent — the same model-selection rule as the Discovery Context call in step 4, but one call per gray-zone ticket, not one call for the whole batch). If the two scores disagree, keep the higher (more conservative) one. If no cheap-model route exists, stop and report the blocker before presenting the approval request, as in step 4.
   - *Pipeline label:* derive the ticket's `pipeline::*` label from its final score: `pipeline::fast` when the score is `≤ story_points.fast_threshold` (default `3`) *and* `Execution: afk`; `pipeline::full` when the score is `≥ story_points.full_threshold` (default `5`) *and* `Execution: afk`. A score `≥13` also means that the slice is not tracer-bullet sized — flag it on the STOP-AND-ASK gate in step 6 as needing further splitting. `hitl` tickets never receive a `pipeline::*` label.
4. **Prepare the Discovery Context (when the parent has `## Relevant Files (Discovery Context)`):** parse that section after drafting the proposed tickets. It is an approved starting context, not a replacement for a ticket's own scope.
   - Assign every listed path to every tracer bullet it materially supports; a shared path may belong to more than one ticket. For each assignment, keep the supplied context and add one short ticket-specific reason. If a path supports no proposed ticket, show it as **unassigned** and stop for the user's decision; never assign it artificially.
   - Build a **Path inventory** for the whole batch. For each Discovery Context path, include the path and list every path under its direct containing directory and under the existing `tests/` and `shared/` directories. Apply the repository's default exclusions while expanding directories: secrets, dependencies, build/dist output, caches, generated/minified files, large logs, databases, temporary data, and unrelated media. Keep an explicitly approved Discovery Context file even if it matches an exclusion, but never expand that excluded category. A Discovery Context file at the repository root is included as that file, never by adding the repository root. Do not read or send file contents or symbol signatures, and do not include paths outside these directories.
   - Make **one cheap-model advisory call** exactly once per batch. If the runtime can pin a model, use `model: haiku` (or the cheapest configured equivalent); otherwise use the runtime's configured cheapest-model route. Pass the proposed ticket titles, scopes, assigned paths, and the Path inventory. Ask it to return only additions: for each ticket, exact paths already present in the Path inventory and one concise reason each. It may add dependencies, especially tests and shared code; it must not remove or move assigned paths, invent paths, or change ticket scope. If no cheap-model route exists, stop and report the blocker before presenting the approval request; never substitute the current model.
   - Add every valid suggested dependency to the Discovery Context of the relevant ticket with its reason. Discard suggestions that are not exact Path inventory paths or do not support that ticket's end-to-end behavior. The per-ticket lists are ready only when every original path is assigned (or explicitly shown as unassigned) and every addition is traceable to the Path inventory.
5. **Draft the agent prompt blocks:** the Task Board's agent prompt carries two fixed blocks, ARCHITECTURE INVARIANTS and IMPLEMENTATION DISCIPLINE (see `docs/agents/agent-prompt.md`). The board takes each block from the epic's `## Architecture invariants` or `## Implementation discipline` section and falls back to the same section of `docs/agents/agent-prompt.md`.
   - Skip a block whose section the epic body already has: keep it as written.
   - For each missing block, draft the section from the spec and the ADRs it cites. Use the project default from `docs/agents/agent-prompt.md` as the starting point when it has one. Write only rules that hold for every ticket of this epic: invariants are architecture and ownership boundaries the tickets must not break; discipline is how an agent works a ticket (what to read first, the test seam, the checks to run). Write each rule as one short list item in English.
   - Leave a block undrafted when the spec gives no rule for it and the project default already fits; say so on the gate.
6. **STOP AND ASK (quiz the user):** present the proposed breakdown as a numbered list. For each ticket, show:
   - **Title:** a short descriptive name;
   - **Blocked by:** which tickets gate it, each with its reason (result dependency or known incompatibility);
   - **Story Points / Pipeline:** for `afk` tickets, the final Fibonacci score and the derived `pipeline::fast`/`pipeline::full` label, flagged `⚠️ score ≥13 — split further` when that applies. Omit for `hitl` tickets — they carry neither a score nor a `pipeline::*` label;
   - **What it delivers:** the end-to-end behavior;
   - **Relevant Files (Discovery Context):** the assigned and advisory-added paths with reasons; omit the field if the parent has no Discovery Context.
   - After the list, show the drafted `## Architecture invariants` and `## Implementation discipline` sections of the epic from step 5, or say which block stays with the epic's existing section or the project default.
   - *Ask the user:* is the granularity right? Are the blocking edges correct? Should anything be merged or split? Does the story-point score feel right, and is the derived pipeline label correct — the user may override the label on the gate without changing the score. Are the drafted prompt blocks right for every ticket of the epic?
   - Stop here until the user approves the breakdown.

##### Phase 2: publishing and summary (after approval)

1. **Publish to the tracker:** the method depends on the configured tracker:
   - **Integration branch:** read the `## Integration Branch` section of the parent epic before writing any child ticket. Copy its exact branch name into every child ticket; if the epic has no integration branch, stop and report the missing prerequisite instead of inferring a branch.
   - **Local files:** append the approved `## Architecture invariants` and `## Implementation discipline` sections from the gate to the epic's `.scratch/<feature-slug>/spec.md`; the board reads that file as the epic body. Write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md` (01, 02...). Use `<local-ticket-template>`. Include the finished per-ticket `Relevant Files (Discovery Context)` list when Discovery Context was present. Set `**Workflow:**` to `status::blocked` if there are blockers, otherwise to `status::ready`. Set `**Execution:**` to `hitl` or `afk` by your best judgment about the ticket (see `docs/agents/triage-labels.md`). For `afk` tickets, set `**Story Points:**` to the final score from step 3 and `**Pipeline:**` to the label approved on the STOP-AND-ASK gate — the derived label, or the user's override if they changed it there; the score itself never changes. Omit both lines entirely for `hitl` tickets. Add `**Task report:** required` unless told to skip it (omit the line entirely if it is not required). `/fast-implement` finds the next ticket by reading the `**Workflow:**` field of each file — a purely linear chain is resolved from top to bottom.
   - **GitHub / GitLab:** `<project-url>`, `<host>`, and `<project-id>` in the GitLab commands are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.
     - Publish one issue per ticket in dependency order using `<issue-template>`. GitHub: `gh issue create --body-file <path>`. GitLab: `glab issue create -R <project-url> --title '<title>' --description-file <path> --yes`, where `<title>` is in single quotes and each apostrophe inside it is written as `'\''` in a POSIX shell or as `''` in PowerShell; the ticket number is the last segment of the issue URL that the command prints. Do not pass the body inline with `--body`/`--description` or a heredoc — it breaks shell quoting (see `docs/agents/git-workflow.md` §1). Record each blocker with its reason: a native dependency on GitHub, a `Blocked by #<M>` line on GitLab; the text fallback carries the same edge and the same reason.
     - Include the finished per-ticket `## Relevant Files (Discovery Context)` section when Discovery Context was present. Keep the exact paths and their reasons; it is the curated starting context of the implementation ticket.
     - Include the finished `## Story Points` section (the approved score) for `afk` tickets; omit the section entirely for `hitl` tickets.
     - Apply labels (see `docs/agents/triage-labels.md` for the full taxonomy): `type::*`, `status::ready` (or `status::blocked` if the ticket is gated by another ticket in this batch), `hitl`/`afk`, `pipeline::fast` or `pipeline::full` for `afk` tickets — the label approved on the STOP-AND-ASK gate, the derived label or the user's override, never applied to `hitl` tickets — and `task-report::required` unless told to skip it. GitLab: `glab issue update <n> -R <project-url> --label '<label>,<label>'`; a label that the project does not have yet is silently created by GitLab with the default color, so `/setup-labels` must have run beforehand.
     - *Grouping:* link every ticket to the parent epic through the tracker's parent link. Do NOT use `epic::<slug>` labels.
       - GitHub: link the ticket to the epic as a **native sub-issue**.
       - GitLab: the `## Parent: #<epic>` section in the ticket plus exactly one `relates_to` link from the ticket to the epic, created right after the ticket: `GITLAB_HOST=<host> glab api --method POST projects/<project-id>/issues/<n>/links -F target_project_id=<numeric-project-id> -F target_issue_iid=<epic> -F link_type=relates_to`. `<numeric-project-id>` is the `id` field of `GITLAB_HOST=<host> glab api projects/<project-id>`; read it once per batch. Blocking edges stay in the `Blocked by #<M>` lines; no links are created between tickets. Epics, `blocks` links, and the native issue hierarchy are GitLab Premium features, and they are not used.
     - *Local mirror:* the specification of the epic already lives in its own folder under `docs/tasks/` (per `docs/agents/artifacts.md`) — first rename that folder to `issue-<epic-id>-<epic-slug>/` if it still contains only the slug. Save the issue body of each published ticket in that folder's `tickets/` subfolder as `tickets/issue-<ID>-<slug>.md` — not flat alongside the specification.
     - *Frontier:* do not trace `Blocked by` by hand to find out what can be taken — query it: the same fields and mechanism as the frontier query of `/wayfinder` for the configured tracker (`docs/agents/issue-tracker.md#wayfinding-operations`), but limited to the child tickets of the epic instead of the children of the map: its GitHub sub-issues, and on GitLab the issues linked to the epic whose description carries `## Parent: #<epic>`. `/fast-implement` runs this same query itself when it is handed an epic instead of a specific ticket.
     - Do not close or rewrite the parent issue of the epic, except to add a short list of the created subtask numbers and the approved `## Architecture invariants` and `## Implementation discipline` sections. Read its current body: GitHub — `gh issue view <epic> --json body --jq .body`; GitLab — the `description` field of `glab issue view <epic> -R <project-url> -F json`. Append the list and the sections and save the result as the specification file of the epic in its `docs/tasks/` folder. Publish that file: GitHub — `gh issue edit <epic> --body-file <path>`; GitLab — `glab issue update <epic> -R <project-url> --description-file <path>`.
2. **Summarize the batch:**
   - Read `language` from `.harness/project.json` (the default is `ru` if the file or the field is missing) — it determines only the "What to build" column below, not the titles or bodies of the published tickets, which stay in the language in which you prepared them.
   - If this runtime supports dispatching a sub-agent pinned to a specific model, send one call with `model: haiku` (the cheapest available, one call per batch) — pass it the title and body of each ticket plus the target language, asking for one concise sentence for each ticket in that language. Otherwise, write the descriptions yourself, with your own model, in the same language.
   - Output the final table that combines all the data. The labels column must list all applied taxonomy tags (for example, `type::feature`, `status::ready`, `afk`, `pipeline::fast`, `task-report::required`).

   | Ticket | What to build | Story Points | Labels |
   |---|---|---|---|
   | <number/link/path> | <one-line summary> | <score, or "—" for `hitl`> | <comma-separated labels> |

---

&lt;local-ticket-template&gt;
### &lt;NN&gt; — <Ticket title>

**What to build:** the end-to-end behavior that this ticket makes work from the user's point of view.
**Blocked by:** the numbers/titles of the tickets that gate this ticket, each with its reason, or "None — can start immediately".
**Integration branch:** the exact branch recorded by the parent epic.

#### Relevant Files (Discovery Context)
- `<path>` — why this ticket needs it (omit this section when the parent has no Discovery Context).

**Category:** type::bug / type::feature / type::refactoring / type::chore / type::security / type::performance / type::hotfix
**Workflow:** status::ready (or status::blocked)
**Execution:** hitl / afk
**Story Points:** Fibonacci score (afk tickets only; omit the line entirely for hitl tickets)
**Pipeline:** pipeline::fast / pipeline::full (afk tickets only, derived from Story Points; omit the line entirely for hitl tickets)
**Task report:** required (omit the line entirely if it is not required)

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
&lt;/local-ticket-template&gt;

&lt;issue-template&gt;
#### Parent: #&lt;epic&gt;
The heading line itself carries the number of the parent epic and serves as a fixed marker for the frontier query: keep it exactly in this form and never translate it. Omit the section if the ticket has no parent epic.

#### Integration branch

The exact integration branch recorded by the parent epic. Child implementation branches start from this branch, and their PRs target it.

#### What to build
The end-to-end behavior that this ticket makes work from the user's point of view.

#### Story Points
The approved Fibonacci score (afk tickets only; omit this section entirely for hitl tickets — the derived pipeline::fast/pipeline::full label is applied on the tracker, not written here).

#### Relevant Files (Discovery Context)
- `<path>` — why this ticket needs it (omit this section when the parent has no Discovery Context).

#### Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2

#### Blocked by
- Blocked by #&lt;M&gt; — one such line per blocking ticket with its reason, or "None — can start immediately".
&lt;/issue-template&gt;

*Note for both templates: `Relevant Files (Discovery Context)` is the only file-path section; keep only the assigned paths and their short reasons. Avoid paths and code fragments everywhere else unless it is a vitally important prototype fragment (keep only the parts that are dense with decisions).*

</div>

## 3. Contracts

- **Input (Input/Brief):** a plan, a specification, or the conversation context; the parent epic and its integration branch; explicit approval of the proposed decomposition.
- **Output (Output/Report):** tracer-bullet tickets with dependencies, labels, story points, pipeline labels, and a local mirror; the final batch table.

## 4. Architecture diagram

![/to-tickets: vertical slices instead of layers](../diagrams/previews/vertical-slices.workflow.png)

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-tickets/SKILL.md)
