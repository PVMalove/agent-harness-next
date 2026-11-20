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

This skill doesn't review the code, commit it, run `qa-gate`, or open the PR for you — there's no single command for any of that on the `hitl` path. Once the code is written, do these yourself, in order:

1. Run `/code-review` (or ask this session to run it) — same two-axis Standards + Spec review `/implement` would run for you on an `afk` ticket. Nothing else triggers it on this path; skipping it means the diff never gets reviewed before the PR.
2. Commit your work with a Semantic Commit Message (`feat:`, `fix:`, ...) and push, per `docs/agents/git-workflow.md` — don't let finished work sit uncommitted or unpushed.
3. Run `/qa-gate` (or ask this session to run it).
4. **GitHub/GitLab-tracked ticket:** open the PR/MR into `<target-branch>` per `docs/agents/git-workflow.md`. Write its body to `.harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md` from the body template directly, or configure and run `pr-composer` manually in the coding application.
   - **Footer:** `Closes #<ID>` or `Related to #<ID>`, chosen by `docs/agents/git-workflow.md` §2 step 6 → Ticket footer. Write the resulting footer and this project's command that resolves the default branch, with real values.
   - **Open it.** GitHub: `gh pr create --base <target-branch> --title '<title>' --body-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md`. GitLab: `glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' --description-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md --yes`; the MR is `!<iid>`, the last segment of the URL it prints.
   - **Task report:** if this ticket carries `task-report::required`, post the completion report when you open the PR/MR, with the format, path and command of `/to-pull-requests` step 6.
   - **After you merge it:** check the merge, then close the issue or verify that it closed, as `docs/agents/git-workflow.md` §2 step 7 → Close the ticket after merge describes. Write this project's tracker commands from that step here, with real values.

   **Local-markdown-tracked ticket:** there's no PR/merge step — once the above all pass, set the ticket file's `**Workflow:**` line to `done` yourself; if it carries `**Task report:** required`, fold the completion summary into that same update.
