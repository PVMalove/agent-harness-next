# Hooks

Hooks are deterministic checks that physically block an action instead of leaving a
recommendation. A rule written only in an instruction can be missed; a rule written as a
hook returns a refusal before the command runs.

The profile is set only in the project configuration, in the `hook_policy` key. Environment variables and
tool parameters do not affect the profile choice.

## Profiles

| Behavior | `minimal` | `standard` | `strict` |
| --- | --- | --- | --- |
| Critical guards | yes | yes | yes |
| Bounded check run | warning | blocks | blocks |
| Impact-change notice on the first touch of a risky path | no | warning | warning |
| Reminder about unreported targeted checks | no | yes | yes |
| Recheck of sensitive paths on every touch | no | no | yes |
| Refusal at high-risk boundaries | no | no | yes |

Without the `hook_policy` key, `standard` applies: the blocking set matches the familiar behavior,
so an existing project does not change mode without an explicit decision. Escalations only raise the profile
for the specified paths or roles — the validator rejects a downgrade.

## Critical guards

These checks block in every profile, including `minimal`:

- **Protected branches.** A direct commit or push to the release branch and to `integration/*` is forbidden: work
  goes into an issue branch, and a human updates the protected branches through a merge.
- **Pull request merge.** The merge command is blocked unconditionally: a human always performs the merge.
- **Public attribution.** Traces of an automated executor are forbidden in commit messages and in
  PR/MR titles and bodies; in tracker text, only attribution is blocked.
- **Policy protection.** Writes to the hooks settings and hooks directories, and changes to the `hook_policy` key
  by an agent tool, are blocked.

## Hooks table

| Hook | Event | What it blocks |
| --- | --- | --- |
| `protect-hook-policy.sh` | `PreToolUse` — Bash, Write, Edit | Edits to the hooks settings and directories and changes to the policy key |
| `block-direct-master.sh` | `PreToolUse(Bash)` | A commit and push to a protected branch; allows only the creation of a new integration branch |
| `block-pr-merge.sh` | `PreToolUse(Bash)` | Any PR/MR merge command; if the command cannot be parsed, the refusal also fires |
| `block-public-attribution.sh` | `PreToolUse(Bash)` | Forbidden information in commit messages, in PR/MR titles and bodies, and in files passed as the body |
| `check-branch-name.sh` | `PreToolUse(Bash)` | Creation of a branch whose name does not match `branch_pattern` |
| `check-worktree-branch-name.sh` | `PreToolUse(EnterWorktree)` | The same name rule for the worktree tool |
| `block-scratch-outside-docs-tasks.sh` | `PreToolUse(Write, Edit)` | Temporary artifacts outside the allowed directories; the PR title and comments — only through a file in an allowed location |
| `require-qa-gate.sh` | `PreToolUse(Bash)` | PR/MR creation if QA did not run or failed for the current tree |
| `require-bounded-check.sh` | `PreToolUse(Bash)` | A full run of the check suite without a summary wrapper; a targeted test is not blocked |
| `block-dangerous-git.sh` | `PreToolUse(Bash)` | Destructive operations: `reset --hard`, `clean -f`, branch deletion, `restore .` |
| `impact-first-touch.sh` | `PreToolUse(Write, Edit)` | Nothing: warns about the first touch of a path whose impact is not computed from the graph |
| `sensitive-path-recheck.sh` | `PreToolUse(Write, Edit)` | Nothing: in `strict`, reports every edit of a sensitive path and writes an evidence record |
| `targeted-check-reminder.sh` | `PreToolUse(Write, Edit)`, `Stop`, `SubagentStop` | Nothing: in `standard` and `strict`, reminds to report targeted checks if files changed after the report |
| `count-skill-usage.sh` | `PreToolUse(Skill)` | Nothing: counts how often skills are called |
| `mark-qa-gate-passed.sh` | `PostToolUse(Bash)` | Nothing: records a QA pass marker for direct command runs |

Separately, a project with the test-author role enabled gets a scoped guard for the test zone: it does not allow
changing tests from the implementing role. It is not part of the standard installation.

## Policy and audit

At approval, the digest of the hooks policy is pinned. So a profile change is visible as a change of the
contract: a reviewed plan describes one policy while execution runs under another, and this is noticed before
publication, not after.

A human changes the profile by editing the project configuration. An agent cannot change either the hooks settings or
the policy key itself — this is blocked in all profiles. The recovery commands (`ledger lock-status`,
`qa clear-stale-lease`, `batch rewind`, `dispatch cancel`) are not blocked by any profile: otherwise there would be
no way out of a refusal.

## Next

- [Concepts: hooks and profiles](../concepts/hooks.md)
- [CLI](cli.md)
- [Workflow](../guides/workflow.md)
