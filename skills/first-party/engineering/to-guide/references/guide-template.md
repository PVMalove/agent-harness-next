# Guide template

Fill every section. In section 5 keep only the commands of this project's tracker and fill in the
real values as `SKILL.md` step 5 describes.

# Implementation Guide: <ticket title/ID>

## 1. Context & Constraints

The architectural rules (ADRs), patterns, and boundaries that apply here — condensed from the ticket/spec and the codebase, not restated in full.

## 2. File Map

- `[Create]` path/to/new/file
- `[Update]` path/to/existing/file

Start from the ticket's `## Relevant Files (Discovery Context)` and `## Contract touchpoints`;
list nothing from its `## Out of scope`.

## 3. Steps & Prompts

Break the implementation into small, compilable chunks. For each:

**Step N: <goal>**

```text
<a complete, ready-to-paste prompt for the human's AI IDE — cites specific existing files to follow, states the acceptance criterion it satisfies>
```

## 4. Verification

How to check this slice works — the exact test command, or a `curl`/manual step — drawn from the ticket's `Action -> Verify` criteria or the spec's `## Acceptance & Verification Criteria`.

## 5. When you're done

This skill doesn't review the code, commit it, run `qa-gate`, or open the PR for you. Once the code is written, do these yourself, in order:

1. Run `/code-review` (or ask this session to run it) — same two-axis Standards + Spec review `/implement` would run for you on an `afk` ticket. Nothing else triggers it on this path; skipping it means the diff never gets reviewed before the PR.
2. Commit your work with a Semantic Commit Message (`feat:`, `fix:`, ...) and push, per `.harness/instructions/git-workflow.md` — don't let finished work sit uncommitted or unpushed.
3. Run `/to-pull-requests <ID>` from the issue branch (or ask this session to run it). It runs `/qa-gate`, picks the footer by `.harness/instructions/git-workflow.md` §2 step 6 → Ticket footer, and opens the PR/MR into `<target-branch>` only after you confirm. If the ticket carries `task-report::required`, `/to-pull-requests` step 6 posts the completion report.
4. Merge the PR/MR yourself, then run `/to-pull-requests <ID>` again and confirm the merge. It checks the merge and closes the ticket as `.harness/instructions/git-workflow.md` §2 step 7 → Close the ticket after merge describes, then unblocks the dependent tickets.

   On a local markdown tracker there is no PR/MR: `/to-pull-requests <ID>` asks you to merge the issue branch into `<target-branch>`, checks the merge and sets the ticket file's `**Workflow:**` line to `done`.
