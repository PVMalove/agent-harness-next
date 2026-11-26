# RCA phase

Read when the RCA phase of `SKILL.md` starts on an error stop. Redact every secret first, as the
skill's Redact section requires, in each step below.

## 1. Why-chain

Ask "why" up to five times, starting from the exact symptom. Each step records:

- **Question** — why did the previous answer happen?
- **Answer** — the cause one level down.
- **Evidence** — one of three kinds: a command with its output, a log line, or a code line as
  `path:line`.

A step without evidence does not count: find the evidence or stop the chain there.

Stop at the first cause that harness code, a harness contract or a harness process controls. A
remedy or error hint that misled you or did not help is itself a harness defect: stop there.

If five steps pass without such a cause, record the last cause found and mark it
`Root cause: unresolved after 5 whys`. That is a valid outcome too.

## 2. Classify the root cause

Pick exactly one class:

- `harness` — harness code, a contract, a process, or a misleading remedy.
- `environment-or-misuse` — the environment (network, credentials, an external service, a machine
  state) or a use of the harness outside its contract.

The class decides the draft: `harness` gets a bug-ticket draft; `environment-or-misuse` gets only
the proposed FMEA entry.

## 3. Write the draft

Write the draft to `docs/tasks/rca-<symptom-slug>/rca-<symptom-slug>.md`: one folder per document,
as `.harness/instructions/artifacts.md` requires. When the bug ticket gets a number, rename the
folder and the file by the same rule. `/docs/tasks/` is gitignored: never commit the draft.

Use this template. Leave out the sections marked `harness only` for `environment-or-misuse`. For
`harness`, run step 4 before you write `Bug ticket draft`.

````markdown
# RCA: <symptom in a few words>

## Stopped ticket
<ticket link> — calling skill: <skill name, or "none: invoked directly">

## Symptom
<exact error, redacted>

## Why-chain
1. Why <question>? — <answer>. Evidence: <command and output | log line | path:line>
2. ...

## Root cause
<cause, or "Root cause: unresolved after 5 whys" with the last cause found>

Class: harness | environment-or-misuse

## Evidence
<commands with output, log lines, path:line references; all redacted>

## Proposed FMEA entry
title = "<slug matching ^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$>"
mode = "<what fails and how it shows up>"
detection = "<how the harness detects the failure>"
recovery = "<do X and retry>"
test = "<identifier of the future recovery test, or: to be written>"
residual_risk = "<what stays unmitigated>"

## Bug ticket draft (harness only)
Title: <title>
Labels: type::bug, rca::done

### RCA
<short symptom, why-chain and root cause; a pointer to the proposed FMEA entry>

## Decision (harness only; filled by the developer)
Target tracker: <this project's tracker | the harness tracker>
Blocks stopped ticket: yes | no
Duplicate of:
Approved:
````

The proposed FMEA entry has exactly the six keys above and no GUID key: only
`python scripts/fmea_catalog.py new <title>` in the harness repository generates the GUID. Never
type one by hand. The phase only proposes the entry; adding it to the catalog goes through the bug
ticket in the harness repository.

Write `recovery` as an action and a retry ("do X and retry"), never as a description of the cause.

Choose `Target tracker: the harness tracker` when the root cause is in the harness but the stopped
work runs in a target project.

## 4. Search for a duplicate (harness only)

Before you write the bug-ticket draft, search the open `type::bug` tickets of the target tracker
for the same root cause. Use "List issues" from `.harness/instructions/issue-tracker.md` for that
tracker with `--label type::bug` and the open state; for the local markdown tracker, search
`.scratch/*/issues/`. Match on the root cause or the FMEA `title`, never on the symptom alone.

On a match, replace `Bug ticket draft` with a `Comment draft` for the existing ticket: the new
symptom, the why-chain and the evidence. Set `Duplicate of: #<N>`.

When the search cannot run (for example, the sandbox blocks the tracker host), write
`Duplicate search: not run (<reason>)` in the draft. Never skip it silently.

## 5. Publish an approved RCA draft

The phase does not wait for an answer: it writes the draft, returns control, and offers publication
in its final message. Run this step only after the developer's explicit "yes" for a specific draft,
in the same session or a later one that names the draft path. Without that "yes", write nothing to
the tracker. A `Class: environment-or-misuse` draft has nothing to publish: the draft with its FMEA
entry is the outcome.

The labels `type::bug` and `rca::done` must exist in the target tracker: `gh issue create --label`
fails on a missing label, and GitLab creates one with a default color. Run `/setup-labels` first
when they are missing.

Follow the tracker's commands in `.harness/instructions/issue-tracker.md`:

- **New ticket.** Write the bug-ticket title and body to a draft file, then run "Create an issue"
  with `--body-file <path>` (GitHub) or `--description-file <path>` (GitLab) and the labels
  `type::bug` and `rca::done`. For the local markdown tracker, create the issue file with a
  `Labels: type::bug, rca::done` line.
- **Duplicate.** Write the comment to `.harness/.sandboxes/pr_body/issue-comment-<N>-<slug>.md` and
  run "Comment on an issue", as `.claude/rules/git-delivery.md` requires: one publication command
  per shell call, and delete the file only after the command succeeds.
- **`Blocks stopped ticket: yes`.** Give the stopped ticket `status::blocked` with "Replace the
  status label", so it keeps exactly one `status::*` label, and add a `Blocked by #<bug>` line to
  its body. On GitHub, also add the native dependency edge from "Blocking" in the same guide.

## 6. Return

End with the fixed line from `SKILL.md`:
`RCA draft: <path>. Continue with the next free ticket.`
