---
name: fast-implement
description: Implements one afk ticket labeled pipeline::fast in this session, test-first, and commits and pushes its issue branch after the developer approves. Use explicitly for a small ticket whose direction is settled; use /implement for pipeline::full and /to-guide for hitl. Never opens a pull request or closes the ticket.
disable-model-invocation: true
---

Invoke only on an explicit request (`/fast-implement`, or `$fast-implement` in Codex). Implement the
ticket in this session with no architect step, no independent QA role, and
no coordinator approval gates. Never open a PR, run `qa-gate`, merge, close the ticket, or commit to `base_branch` or an
`integration/*` branch. On GitLab, every `glab` command takes `-R <project-url>`; the placeholders
are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.

## Resolve the ticket

1. **A named ticket** (issue number, URL, or `.scratch/<feature>/issues/NN-*.md`): use it. Stop on
   `hitl` (see `docs/agents/triage-labels.md`) and offer `/to-guide`. Require `pipeline::fast`, or
   `**Pipeline:** pipeline::fast` on the local tracker; without it, or on `pipeline::full`, offer `/implement`.
2. **An epic** (`status::specs`, or the parent of a decomposition): pick the first open, unblocked,
   unclaimed `afk` + `pipeline::fast` child of the lowest execution wave. On GitHub/GitLab use the
   `/wayfinder` frontier query (`docs/agents/issue-tracker.md#wayfinding-operations`) scoped to the
   epic's children, and claim the ticket (`gh issue edit <n> --add-assignee @me`; GitLab
   `glab issue update <n> -R <project-url> --assignee @me`) before any other write. On the local
   tracker take the first issue file in filename order with `**Workflow:** status::ready`. If none
   qualifies, say why: only `hitl` tickets remain (offer `/to-guide`), only `pipeline::full` ones
   remain (offer `/implement`), nothing is unblocked, or everything is claimed.
3. **Nothing named:** when `docs/agents/git-workflow.md` has an Issue First rule, stop and ask for an
   existing ticket, or to prepare one with `/to-spec`, `/publish-epic` and `/to-tickets`.

## Pre-flight

1. **Blockers.** Read them from the tracker (native dependencies, `Blocked by` lines or the
   `**Blocked by:**` field). If any is open, stop, name it, and make sure the ticket is `status::blocked`.
2. **Mark it in progress** before creating the branch or editing any file. Replace the `status::*`
   label; a ticket carries exactly one:
   - GitHub: `gh issue edit <n> --remove-label status::ready --remove-label status::blocked --add-label status::in-progress`,
     then confirm with `gh issue view <n> --json labels --jq '[.labels[].name]'`.
   - GitLab: `glab issue update <n> -R <project-url> --unlabel status::ready,status::blocked --label status::in-progress`,
     then confirm with `glab issue view <n> -R <project-url> -F json`.
   - Local tracker: set the `**Workflow:**` line to `status::in-progress`.
   A failed label write stops the run.
3. **Integration branch.** Take it from the ticket's `## Integration Branch` section (the
   `**Integration branch:**` line on the local tracker), else from its parent epic. A ticket without
   an epic uses `base_branch`. A missing value for a child ticket is a blocker; never infer it.
4. **Issue branch.** The current branch must match `branch_pattern`. Otherwise fetch the integration
   branch, create `feature/issue-<ID>-<slug>` from it, and push it with `git push -u origin <branch>`.
5. **Scope.** The ticket's `## Relevant Files (Discovery Context)`, `## Contract touchpoints` and
   `## Out of scope` bound the change, and its `Action -> Verify` criteria are its checks. A change
   outside them needs the developer's explicit approval before it is made.

## Implement

Run steps 1–4 under the `developer` skill; pre-flight already meets its prerequisites. After step
4, show the developer that skill's evidence (changes, checks, unverified items, risks, blockers)
before asking about review. Steps 5–7 and the handoff stay with this skill; the `developer` skill
never performs them.

1. **Agree the seams before the first test.** Restate the seam the ticket or spec names, or propose
   one with its public signatures and fixtures, and wait for the developer to confirm it.
2. Read `../tdd/references/test-author.md` and run its short-route preflight once before the first
   test. Neither route adds a coordinator, architect or QA step.
3. Build test-first with `/tdd` at the agreed seams.
4. Run typechecking and single test files as you go. Finish with the checks the `developer` skill
   requires, including every `Verify` command; the full suite runs in `/qa-gate` before the PR.
   That gate runs only `qa_gate_commands`: `pre_qa_commands` and the QA workflow overlays apply to
   `/implement` alone.
5. Ask the developer: “Провести code review?” Wait for the answer. On yes, run `/code-review`,
   address the requested changes, and rerun the relevant tests. On no, record the decline.
6. Ask the developer for explicit permission to commit and push. Wait for the answer.
7. After approval, check that the branch still matches `branch_pattern` and is neither `base_branch`
   nor `integration/*`. Commit with a Semantic Commit Message, push to the issue branch, and report
   the result.

## Finish

After a successful push, offer `/to-pull-requests <ticket>` as the next command. Never invoke it.
Leave `status::in-progress` on the ticket: `/to-pull-requests` closes it and moves its unblocked
dependents to `status::ready` after the merge.
