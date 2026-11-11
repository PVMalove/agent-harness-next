# To Guide — Into a guide

## 1. Name and localization

- **English name:** `To Guide`
- **Russian translation:**

```text
В руководство
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: to-guide
description: Turn a hitl ticket or a specification into a step-by-step manual implementation guide with ready-to-paste prompts for an AI IDE (Cursor, Copilot Chat). For tickets that a human will write by hand, not an agent.
disable-model-invocation: true
```

### Into a guide (preparing a manual implementation)

Turn a specification or a tracer-bullet ticket into a developer guide with ready-to-use prompts for an AI-assisted IDE. This is the matching `hitl` route for `/implement` and `/fast-implement`: they take `afk` tickets, and an agent writes the code; `/to-guide` takes `hitl` tickets and instead hands the human a navigator checklist. After this skill runs, coding, code review, `qa-gate`, and the PR all remain the human's task — the skill does not perform them and is not invoked again on this ticket (the guide it creates names the exact commands in its closing section).

#### Process

1. **Read the source.** Get the ticket that the user named — an issue number, a URL, or a `.scratch/<feature>/issues/NN-*.md` path (see `docs/agents/issue-tracker.md`). If it carries `status::blocked`, check the blockers the same way `/implement` does: if even one is still open, stop and tell the user which ones, instead of preparing a guide for a ticket that cannot actually be started yet. If the ticket has `status::specs` instead of `status::ready`, or does not carry `hitl`, tell the user and ask whether to continue anyway — this skill expects a fully specified ticket that is routed to a human (see `docs/agents/triage-labels.md`).
2. **Explore the codebase.** Identify the exact files to create or change to complete the ticket — do not guess only from the ticket text. Use the project's domain glossary and follow every ADR in the affected area.
3. **Claim the ticket.** Assign the ticket to the maintainer (`gh issue edit <n> --add-assignee @me` on GitHub, `glab issue update <n> -R <project-url> --assignee @me` on GitLab, or the equivalent of the local tracker) before any other write — the same convention that `/wayfinder` and `/fast-implement` use, so that a parallel session does not pick the same `hitl` ticket. On GitLab, every `glab` command takes `-R <project-url>`, and every `glab api` call is written as `GITLAB_HOST=<host> glab api projects/<project-id>/...`; these placeholders are defined in `docs/agents/issue-tracker.md` → GitLab → Conventions.
4. **Mark it as in progress.** A ticket carries exactly one `status::*` label (see `docs/agents/triage-labels.md`), so replace the current one — `status::ready`, a `status::blocked` whose blockers step 1 found closed, or a `status::specs` that the user agreed to continue from — instead of adding a second:
   - **GitHub:** `gh issue edit <n> --remove-label status::ready --remove-label status::blocked --remove-label status::specs --add-label status::in-progress`, then confirm with `gh issue view <n> --json labels --jq '[.labels[].name]'` that `status::in-progress` is the only `status::*` label.
   - **GitLab:** `glab issue update <n> -R <project-url> --unlabel status::ready,status::blocked,status::specs --label status::in-progress`, then confirm with `glab issue view <n> -R <project-url> -F json` that `status::in-progress` is the only `status::*` label in its `labels`.
   - **Local tracker:** set the file's `**Workflow:**` line to `status::in-progress`.
   - If the label write fails, stop and report it.
5. **Prepare the guide** using `<guide-template>` below. In its section 5, keep only the commands of this project's tracker and fill in the real values of `<project-url>`, `<host>`, `<project-id>`, `<target-branch>`, `<ID>`, `<title>`, and `<slug>` (`<title>` stays in single quotes; write each apostrophe as `'\''`, or as `''` if the human's shell is PowerShell) — the human copies these commands without editing them; only the PR/MR number `<n>`/`<iid>` stays a placeholder until the PR/MR exists. Write the guide in the language set by the `language` field in `.harness/project.json` (the default is `ru` if the file or the field is missing). Unlike the summary table of `/to-tickets`, this area is not narrow — write the whole document, including the prompts, in that language: it is a local artifact for a human maintainer to read, not a ticket published to an external tracker. Save it under `docs/tasks/` following the naming convention in `docs/agents/artifacts.md` (ticket ID + descriptive slug) — if the ticket belongs to an epic, into that epic's folder `docs/tasks/issue-<epic-id>-<epic-slug>/`, next to the ticket's own file.

#### Rules for the prompts

- Every prompt must be explicit, self-contained, and tell the human's AI IDE *exactly* what to do — the human will copy-paste it verbatim, without editing it first.
- Point the IDE at existing code to imitate: "follow the pattern in `<file>`" is better than a description of the pattern.
- Make every step small enough to compile and verify on its own — the whole point is narrow, verifiable pieces, the same discipline as the vertical slices of `/to-tickets`.
- In every prompt, ask for the test first — this repository requires TDD (`docs/agents/git-workflow.md`) regardless of who writes the code, and every other route must say so out loud too (`/fast-implement` through `/tdd`, `/implement` through its batch Definition of Done), so state it explicitly instead of assuming the defaults of the human's AI IDE.

&lt;guide-template&gt;

### Implementation guide: <ticket title/ID>

#### 1. Context and constraints

The architectural rules (ADRs), patterns, and boundaries that apply here — condensed from the ticket/specification and the codebase, not restated in full.

#### 2. File map

- `[Create]` path/to/new/file
- `[Update]` path/to/existing/file

#### 3. Steps and prompts

Break the implementation into small, compilable parts. For each one:

**Step N: <goal>**

```text
<a complete, ready-to-paste prompt for the human's AI IDE — cites specific existing files to follow, states the acceptance criterion it satisfies>
```

#### 4. Verification

How to check that this slice works: the exact test command, or a `curl`/manual step taken from the ticket's acceptance criteria or the Testing Decisions of the specification.

#### 5. When you are done

This skill does not review the code, does not create a commit, does not run `qa-gate`, and does not open the PR for you — there is no single command for all of that on the `hitl` route. Once the code is written, do it yourself, in order:

1. Run `/code-review` (or ask this session to run it) — the same two-axis Standards + Spec review that `/implement` would run for an `afk` ticket. Nothing else triggers it on this route; skipping it means the diff is not reviewed before the PR.
2. Create a commit of your work with a Semantic Commit Message (`feat:`, `fix:`, ...) and push it per `docs/agents/git-workflow.md` — do not leave finished work without a commit or a push.
3. Run `/qa-gate` (or ask this session to run it).
4. **GitHub/GitLab-tracked ticket:** open the PR/MR into `<target-branch>` per `docs/agents/git-workflow.md`. Write its body to `.harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md` from the body template directly, or configure and run `pr-composer` manually in the coding application.
   - **Footer:** `Closes #<ID>` only when `<target-branch>` is the default branch (GitHub: `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`; GitLab: the `default_branch` field of `GITLAB_HOST=<host> glab api projects/<project-id>`), otherwise `Related to #<ID>`. GitLab closes an issue by `Closes #<ID>` only when the MR lands in the default branch.
   - **Open it.** GitHub: `gh pr create --base <target-branch> --title '<title>' --body-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md`. GitLab: `glab mr create -R <project-url> --target-branch <target-branch> --title '<title>' --description-file .harness/.sandboxes/pr_body/pr-body-<ID>-<slug>.md --yes`; the MR is `!<iid>`, the last segment of the URL that the command prints.
   - **Completion report:** if the ticket carries `task-report::required`, publish the completion report when you open the PR/MR. Write it to `.harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`, then GitHub: `gh issue comment <ID> --body-file .harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`; GitLab: `GITLAB_HOST=<host> glab api projects/<project-id>/issues/<ID>/notes -F body=@.harness/.sandboxes/pr_body/issue-comment-<ID>-<slug>.md`.
   - **After your merge:** check it (GitHub: `gh pr view <n> --json state,baseRefName`, `state` is `MERGED` and `baseRefName` is `<target-branch>`; GitLab: `glab mr view <iid> -R <project-url> -F json`, `state` is `merged` and `target_branch` is `<target-branch>`). For `Related to #<ID>`, close the issue — GitHub: `gh issue close <ID> --reason completed`; GitLab: `glab issue close <ID> -R <project-url>`. For `Closes #<ID>`, verify that the issue is closed — GitHub: `gh issue view <ID> --json state` (`CLOSED`); GitLab: `glab issue view <ID> -R <project-url> -F json` (`state` is `closed`; GitLab closes it asynchronously, so read it once more if it still shows `opened`) — and close it with the same command if that did not happen.

   **Local Markdown-tracked ticket:** there is no PR/merge step — once everything above passes, set the ticket file's `**Workflow:**` line to `done` yourself; if it carries `**Task report:** required`, fold the completion summary into that same update.

&lt;/guide-template&gt;

</div>

## 3. Contracts

- **Input (Input/Brief):** a `hitl` ticket or a specification, the acceptance criteria, the blocking state, and the repository conventions.
- **Output (Output/Report):** a local step-by-step guide under `docs/tasks/` with a file map, TDD prompts, verification, and a manual route to the PR.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/to-guide/SKILL.md)
